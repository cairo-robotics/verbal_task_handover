import pygame
from treasure_hunt.visualization.utils import *

class ModuleInterface:
    def __init__(self, width, height):
        self.width = width
        self.height = height

class WireSprite:
    def __init__(self, rgb, x, y, width, height):
        self.color = rgb
        self.rect = pygame.Rect(x, y, width, height)

class WireModuleInterface(ModuleInterface):
    def __init__(self, wire_module, game_width, game_height):
        super().__init__(game_width, game_height)

        self.wire_module = wire_module

        self.COLOR_MAPPING = {
            "red" : (255, 0, 0),
            "blue" : (0, 0, 255),
            "yellow" : (255, 255, 0),
            "black" : (0, 0, 0),
            "white" : (255, 255, 255),
            "green" : (0, 255, 0)
        }

        self.wire_sprites = self.create_wire_sprites(game_width, game_height)

    def create_wire_sprites(self, game_width, game_height):
        wire_sprites = []

        x_offset = 15
        y_interval = game_height // (self.wire_module.num_wires+1)

        for i, wire in enumerate(self.wire_module.wires):
            wire_sprites.append(WireSprite(self.COLOR_MAPPING[wire], x_offset, (i+1) * y_interval, game_width-x_offset*2, 5))
        return wire_sprites

    def render(self):
        game_surface = pygame.Surface((self.width, self.height))
        game_surface.fill((255, 255, 255))
        font = pygame.font.SysFont("Arial", 12)
        
        for i, wire_sprite in enumerate(self.wire_sprites):
            pygame.draw.rect(game_surface, wire_sprite.color, wire_sprite.rect)
            
            # Render number labels next to each wire
            label = font.render(str(i+1), True, (255, 0, 0))
            label_rect = label.get_rect()
            label_rect.centery = wire_sprite.rect.centery
            label_rect.left = game_surface.get_rect().left + 2
            # label_rect.right = wire_sprite.rect.left - 6
            game_surface.blit(label, label_rect)
            
            if i == self.wire_module.cut_wire:
                # add a "mask" in the middle of the wire rect to indicate it's cut
                cut_rect = wire_sprite.rect.copy()
                cut_rect.width = 30
                cut_rect.center = wire_sprite.rect.center
                pygame.draw.rect(game_surface, (255, 255, 255), cut_rect)
        return game_surface

class PasswordModuleVisualizer(ModuleInterface):
    def __init__(self, password_module, textbox_sprite, game_width, game_height):
        super().__init__(game_width, game_height)

        self.password_module = password_module
        self.textbox_sprite = scale_to_width(textbox_sprite, game_width)
        self.font = pygame.font.SysFont("Arial", 12)
        self.game_width = game_width
        self.game_height = game_height

    def render(self):
        game_surface = self.textbox_sprite.copy()

        # Render the text from self.password_module.input onto the textbox sprite
        text_surface = self.font.render(self.password_module.input, True, (0, 0, 0))
        text_rect = text_surface.get_rect()
        text_rect.center = game_surface.get_rect().center

        game_surface.blit(text_surface, text_rect)

        return game_surface
