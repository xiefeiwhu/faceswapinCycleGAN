import torch.nn as nn
from torch.autograd import Variable
import block
import torch
import loss
import itertools
import os
import numpy as np
import torchvision.transforms as transforms
from PIL import Image

class Encoder(nn.Module):

    def __init__(self):

        super(Encoder, self).__init__()

        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels=3, out_channels=64,
                      kernel_size=3, bias=False, stride=1, padding=0),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
        )
        

        self.conv2 = nn.Sequential(
            nn.Conv2d(in_channels=64, out_channels=128,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
        )

        self.conv3 = nn.Sequential(
            nn.Conv2d(in_channels=128, out_channels=256,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
        )

        self.sablock1 = block.SABlock(dim_in=256, activation='relu')

        self.conv4 = nn.Sequential(
            nn.Conv2d(in_channels=256, out_channels=512,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(512),
            nn.ReLU(inplace=True),
        )

        self.sablock2 = block.SABlock(dim_in=512, activation='relu')

        self.conv5 = nn.Sequential(
            nn.Conv2d(in_channels=512, out_channels=1024,
                      kernel_size=3, bias=False, stride=1, padding=0),
            nn.BatchNorm2d(1024),
            nn.ReLU(inplace=True),
        )

        self.fc1 = nn.Linear(1024*4*4, 1024, bias=False)
        
        self.bn1 = nn.BatchNorm1d(1024)

        self.fc2 = nn.Linear(1024, 1024*4*4, bias=False)
        
        self.bn2 = nn.BatchNorm1d(1024*4*4)

        self.conv6 = nn.Sequential(
            nn.Conv2d(in_channels=1024, out_channels=2048,
                      kernel_size=1, bias=False, stride=1, padding=0),
            nn.BatchNorm2d(2048),
            nn.ReLU(inplace=True),
        )

        self.upscaleblock = nn.PixelShuffle(2)

    def forward(self, x):

        x = self.conv1(x)

        x = self.conv2(x)

        x = self.conv3(x)

        x, _ = self.sablock1(x)

        x = self.conv4(x)

        x, _ = self.sablock2(x)
        
        x = self.conv5(x)
        
        x = x.view([-1,1024*4*4])

        x = self.fc1(x)
        
        x = self.bn1(x)

        x = self.fc2(x)
        
        x = self.bn2(x)

        x = x.view([-1, 1024, 4, 4])

        x = self.conv6(x)

        x = self.upscaleblock(x)
        
        assert x.shape[1:] == (512,8,8), x.shape

        return x


class Decoder(nn.Module):

    def __init__(self, dim_in=512):
        super(Decoder, self).__init__()

        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels=dim_in, out_channels=256 *
                      2*2, kernel_size=3, bias=False, stride=1, padding=1),
            nn.BatchNorm2d(1024),
            nn.LeakyReLU(inplace=True),
        )

        self.upscaleblock1 = nn.PixelShuffle(2)

        self.conv2 = nn.Sequential(
            nn.Conv2d(in_channels=256, out_channels=128*2 *
                      2, kernel_size=3, bias=False, stride=1, padding=1),
            nn.BatchNorm2d(512),
            nn.LeakyReLU(inplace=True),
        )

        self.upscaleblock2 = nn.PixelShuffle(2)

        self.sablock1 = block.SABlock(dim_in=128, activation=None)

        self.conv3 = nn.Sequential(
            nn.Conv2d(in_channels=128, out_channels=64*2*2,
                      kernel_size=3, bias=False, stride=1, padding=1),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(inplace=True),
        )

        self.upscaleblock3 = nn.PixelShuffle(2)

        self.resblock = block.ResidualBlock(dim_in=64)
        
        self.bn = nn.BatchNorm2d(64)

        self.sablock2 = block.SABlock(dim_in=64, activation=None)

        self.conv4 = nn.Sequential(
            nn.Conv2d(in_channels=64, out_channels=1,
                      kernel_size=3, stride=1, padding=1),
            nn.Sigmoid(),
        )

        self.conv5 = nn.Sequential(
            nn.Conv2d(in_channels=64, out_channels=3,
                      kernel_size=3, stride=1, padding=1),
            nn.Tanh(),
        )

    def forward(self, x):
        
        assert x.shape[1:] == (512,8,8), x.shape 

        x = self.conv1(x)
        x = self.upscaleblock1(x)

        x = self.conv2(x)
        x = self.upscaleblock2(x)

        x, _ = self.sablock1(x)

        x = self.conv3(x)
        x = self.upscaleblock3(x)

        x = self.resblock(x)
        
        x = self.bn(x)

        x, _ = self.sablock2(x)

        mask = self.conv4(x)
        
        assert mask.shape[1:] == (1, 64, 64), mask.shape

        output = self.conv5(x)
        
        assert output.shape[1:] == (3, 64, 64), output.shape

        return output, mask


class Discriminator(nn.Module):

    def __init__(self, dim_in):
        super(Discriminator, self).__init__()

        self.conv1 = nn.Sequential(
            nn.Conv2d(in_channels=dim_in, out_channels=64,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(inplace=True),
        )

        self.conv2 = nn.Sequential(
            nn.Conv2d(in_channels=64, out_channels=128,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(inplace=True),
        )

        self.sablock1 = block.SABlock(128, activation=None)

        self.conv3 = nn.Sequential(
            nn.Conv2d(in_channels=128, out_channels=256,
                      kernel_size=3, bias=False, stride=2, padding=0),
            nn.BatchNorm2d(256),
            nn.LeakyReLU(inplace=True),
        )

        self.sablock2 = block.SABlock(256, activation=None)

        self.conv4 = nn.Sequential(
            nn.Conv2d(in_channels=256, out_channels=1,
                      kernel_size=5, bias=False, stride=1, padding=0),
            nn.BatchNorm2d(1),
        )

    def forward(self, x):
        
        assert x.shape[1:] == (3,64,64), x.shape

        x = self.conv1(x)
        x = self.conv2(x)

        x, _ = self.sablock1(x)
        x = self.conv3(x)

        x, _ = self.sablock2(x)
        x = self.conv4(x)

        return x

    
class CycleGAN(nn.Module):
    
    def __init__(self, vggface, vggface_for_pl, config):
        
        super(CycleGAN, self).__init__()
        
        self.EncoderAB = Encoder()
        self.DecoderA = Decoder()
        self.DecoderB = Decoder()
        
        self.model_names = ['EncoderAB', 'DecoderA', 'DecoderB', 'DiscriminatorA', 'DiscriminatorB']
        self.loss_names = ['loss_D_A', 'loss_D_B', 'loss_G_A', 'loss_G_B', 'loss_Cycle_A', 'loss_Cycle_B', 
                           'loss_G_adversarial_A', 'loss_G_reconstruction_A', 'loss_G_perceptual_A', 'loss_G_mask_A',
                           'loss_G_adversarial_B', 'loss_G_reconstruction_B', 'loss_G_perceptual_B', 'loss_G_mask_B',
                           'loss_G_edge_A', 'loss_G_edge_B', 'loss_G_eye_A', 'loss_G_eye_B',
                          ]
        self.isTrain = config['isTrain']
        self.loss_weight_config = config['loss_weight_config']
        self.loss_config = config['loss_config']
        self.vggface_for_pl = vggface_for_pl
        self.optimizers = []
        self.save_dir = config['save_dir']
        self.vggface = vggface
        self.batchsize = config['batchsize']
        
        if self.isTrain:
            self.DiscriminatorA = Discriminator(3)
            self.DiscriminatorB = Discriminator(3)
            
            self.optimizer_G = torch.optim.Adam(itertools.chain(self.EncoderAB.parameters(), self.DecoderA.parameters(),
                                                                self.DecoderB.parameters()), lr=self.loss_config['lr_factor']*config['G_lr'], betas=(0.9, 0.999))       
            self.optimizer_D = torch.optim.Adam(itertools.chain(self.DiscriminatorA.parameters(), self.DiscriminatorB.parameters()),
                                                                 lr=self.loss_config['lr_factor']*config['D_lr'], betas=(0.9, 0.999)) 
            self.optimizer_Cycle = torch.optim.Adam(itertools.chain(self.EncoderAB.parameters(), self.DecoderA.parameters(),
                                                    self.DecoderB.parameters(),self.DiscriminatorA.parameters(),
                                                    self.DiscriminatorB.parameters()), lr=config['C_lr'], betas=(0.9, 0.999))
            
            self.optimizers.append(self.optimizer_G)
            self.optimizers.append(self.optimizer_D)
            self.optimizers.append(self.optimizer_Cycle)
        
    def set_input(self, inputdata):
        
        self.warpedA = inputdata['warpedA'].cuda()
        self.warpedB = inputdata['warpedB'].cuda()
        self.realA = inputdata['realA'].cuda()
        self.realB = inputdata['realB'].cuda()
        
        if self.loss_config['edgeloss_on'] or self.loss_config['eyeloss_on']:
            self.mask_eye_A = inputdata['eyemaskA'].cuda()
            self.mask_eye_A = inputdata['eyemaskA'].cuda()
            
    def display_train_data(self, inputdata):
        
        # display the image before train
        print('image before training')
        
        # [::-1,:,:] for bgr to rgb, transpose to get h*w*c order image format, fromarray() to get w*h*c order Image type object
        display(Image.fromarray((np.concatenate(tuple(inputdata['realA'].numpy()[x] for x in range(self.batchsize)), 
                                               axis=2)[::-1,:,:].transpose(1,2,0)*255).astype('uint8')))
        
        display(Image.fromarray((np.concatenate(tuple(inputdata['warpedA'].numpy()[x] for x in range(self.batchsize)), 
                                               axis=2)[::-1,:,:].transpose(1,2,0)*255).astype('uint8')))
        
        display(Image.fromarray((np.concatenate(tuple(inputdata['realB'].numpy()[x] for x in range(self.batchsize)), 
                                               axis=2)[::-1,:,:].transpose(1,2,0)*255).astype('uint8')))
        
        display(Image.fromarray((np.concatenate(tuple(inputdata['warpedB'].numpy()[x] for x in range(self.batchsize)), 
                                               axis=2)[::-1,:,:].transpose(1,2,0)*255).astype('uint8')))
        
    def display_forward(self):
        
        with torch.no_grad():
            self.displayAoutput, self.displayAmask = self.DecoderA(self.EncoderAB(self.realB))
            self.displayBoutput, self.displayBmask = self.DecoderB(self.EncoderAB(self.realA))

            self.displayA = self.displayAmask * self.displayAoutput + (1 - self.displayAmask) * self.realB
            self.displayB = self.displayBmask * self.displayBoutput + (1 - self.displayBmask) * self.realA 
            
    def forward(self):
              
        if not self.isTrain or self.loss_config['cyclegan_on']:
            self.warpedA = self.realB
            self.warpedB = self.realA
            
        # mask(Alpha) output and BGR output
        self.outputA, self.maskA = self.DecoderA(self.EncoderAB(self.warpedA))
        
        self.outputB, self.maskB = self.DecoderB(self.EncoderAB(self.warpedB))
        
        # combine mask and output to get fake result
        self.fakeA = self.maskA * self.outputA + (1 - self.maskA) * self.warpedA
        self.fakeB = self.maskB * self.outputB + (1 - self.maskB) * self.warpedB  
        
        if self.isTrain:
            self.fakeApred = self.DiscriminatorA(self.fakeA)
            self.fakeBpred = self.DiscriminatorB(self.fakeB)
            self.realApred = self.DiscriminatorA(self.realA)
            self.realBpred = self.DiscriminatorB(self.realB)
            self.outputApred = self.DiscriminatorA(self.outputA)
            self.outputBpred = self.DiscriminatorB(self.outputB)

        if self.loss_config['cyclegan_on']:
            
            self.cycleA = self.DecoderA(self.EncoderAB(self.outputB))[0]
            self.cycleB = self.DecoderB(self.EncoderAB(self.outputA))[0]
            
    def backward_D_A(self):
        
        self.loss_D_A = loss.adversarial_loss_discriminator(self.fakeApred, self.outputApred, self.realApred, method='L2', loss_weight_config=self.loss_weight_config)
        self.loss_D_A.backward(retain_graph=True)
        
    def backward_D_B(self):
        
        self.loss_D_B = loss.adversarial_loss_discriminator(self.fakeBpred, self.outputBpred, self.realBpred, method='L2', loss_weight_config=self.loss_weight_config)
        self.loss_D_B.backward(retain_graph=True)
      
    def backward_G_A(self):
        
        self.loss_G_adversarial_A = loss.adversarial_loss_generator(self.fakeApred, self.outputApred, method='L2', loss_weight_config=self.loss_weight_config)
        
        self.loss_G_reconstruction_A = loss.reconstruction_loss(self.outputA, self.realA, method='L1', loss_weight_config=self.loss_weight_config)
        
        self.loss_G_mask_A = loss.mask_loss(self.maskA, threshold=self.loss_config['mask_threshold'], method='L1', loss_weight_config=self.loss_weight_config)
        
        self.loss_G_A = self.loss_G_adversarial_A + self.loss_G_reconstruction_A + self.loss_G_mask_A
        
        if self.loss_config['pl_on']:
            self.loss_G_perceptual_A = loss.perceptual_loss(self.realA, self.fakeA, self.vggface,self.vggface_for_pl, method='L2', loss_weight_config=self.loss_weight_config)
            self.loss_G_A += self.loss_G_perceptual_A
            
        if self.loss_config['edgeloss_on']:
            self.loss_G_edge_A = loss.edge_loss(self.outputA, self.realA, self.mask_eye_A, method='L1', loss_weight_config=self.loss_weight_config)
            self.loss_G_A += self.loss_G_edge_A
            
        if self.loss_config['eyeloss_on']:
            self.loss_G_eye_A = loss.eye_loss(self.outputA, self.realA, self.mask_eye_A, method='L1', loss_weight_config=self.loss_weight_config)
            self.loss_G_A += self.loss_G_eye_A
            
        self.loss_G_A.backward(retain_graph=True)
        
    def backward_G_B(self):
        
        self.loss_G_adversarial_B = loss.adversarial_loss_generator(self.fakeBpred, self.outputApred, method='L2', loss_weight_config=self.loss_weight_config)
        
        self.loss_G_reconstruction_B = loss.reconstruction_loss(self.outputB, self.realB, method='L1', loss_weight_config=self.loss_weight_config)
       
        self.loss_G_mask_B = loss.mask_loss(self.maskB, threshold=self.loss_config['mask_threshold'], method='L1', loss_weight_config=self.loss_weight_config)
        
        self.loss_G_B = self.loss_G_adversarial_B + self.loss_G_reconstruction_B + self.loss_G_mask_B
        
        if self.loss_config['pl_on']:
            self.loss_G_perceptual_B = loss.perceptual_loss(self.realB, self.fakeB, self.vggface, self.vggface_for_pl, method='L2', loss_weight_config=self.loss_weight_config)
            self.loss_G_B += self.loss_G_perceptual_B

        if self.loss_config['edgeloss_on']:
            self.loss_G_edge_B = loss.edge_loss(self.outputB, self.realB, self.mask_eye_B, method='L1', loss_weight_config=self.loss_weight_config)
            self.loss_G_B += self.loss_G_edge_B
            
        if self.loss_config['eyeloss_on']:
            self.loss_G_eye_B = loss.eye_loss(self.outputB, self.realB, self.mask_eye_B, method='L1', loss_weight_config=self.loss_weight_config)
            self.loss_G_B += self.loss_G_eye_B
            
        self.loss_G_B.backward(retain_graph=True)
        
    def backward_Cycle_A(self):
        
        self.loss_Cycle_A = loss.cycle_consistency_loss(self.realA, self.cycleA, method='L1', loss_weight_config=self.loss_weight_config)
        
        self.loss_Cycle_A.backward(retain_graph=True)
        
    def backward_Cycle_B(self):
        
        self.loss_Cycle_B = loss.cycle_consistency_loss(self.realB, self.cycleB, method='L1', loss_weight_config=self.loss_weight_config)
        
        self.loss_Cycle_B.backward(retain_graph=True)
        
    def optimize_parameter(self):
    
        self.forward()
        
        self.set_requires_grad([self.EncoderAB, self.DecoderA, self.DecoderB], False)
        
        self.optimizer_D.zero_grad()
        self.backward_D_A()
        self.backward_D_B()
        self.optimizer_D.step()
        
        self.set_requires_grad([self.EncoderAB, self.DecoderA, self.DecoderB], True)
        
        self.set_requires_grad([self.DiscriminatorA, self.DiscriminatorB], False)
        
        if self.loss_config['cyclegan_on']: 
            
            self.optimizer_Cycle.zero_grad()
            self.backward_Cycle_A()
            self.backward_Cycle_B()
            self.optimizer_Cycle.step()
                    
        else:
            self.optimizer_G.zero_grad()
            self.backward_G_A()
            self.backward_G_B()
            self.optimizer_G.step()
            
        self.set_requires_grad([self.DiscriminatorA, self.DiscriminatorB], True)
            
    def set_requires_grad(self, nets, requires_grad=False):
        """Set requies_grad=Fasle for all the networks to avoid unnecessary computations
        Parameters:
            nets (network list)   -- a list of networks
            requires_grad (bool)  -- whether the networks require gradients or not
        """
        if not isinstance(nets, list):
            nets = [nets]
        for net in nets:
            if net is not None:
                for param in net.parameters():
                    param.requires_grad = requires_grad
        
    def initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                torch.nn.init.xavier_uniform_(m.weight, gain=1)
                
    def display_loss(self, epoch):
        for name in self.loss_names:
            if isinstance(name, str):
                if hasattr(self, name):
                    loss = getattr(self, name)
                    print(f'{name}: {loss.cpu().item()}')
                    del loss

    def save_networks(self, epoch):
        
        for name in self.model_names:
            if isinstance(name, str):
                save_filename = f'{epoch}_net_{name}.pth'
                save_path = os.path.join(self.save_dir, save_filename)
                net = getattr(self, name)
                torch.save(net.cpu().state_dict(), save_path)
                    
    def load_networks(self, epoch):
        for name in self.model_names:
            if isinstance(name, str):
                
                load_filename = '%s_net_%s.pth' % (epoch, name)
                load_path = os.path.join(self.save_dir, load_filename)
                
                net = getattr(self, name)
                
                if isinstance(net, torch.nn.DataParallel):
                    net = net.module
                    
                print('loading the model from %s' % save_dir)
                state_dict = torch.load(load_path)
                
                if hasattr(state_dict, '_metadata'):
                    del state_dict._metadata
                    
                net.load_state_dict(state_dict)
