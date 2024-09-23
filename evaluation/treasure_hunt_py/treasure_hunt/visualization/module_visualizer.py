import pygame

class ModuleInterface:
    def __init__(self):
        pass

class WireSprite:
    def __init__(self, rgb, x, y, width, height):
        self.color = rgb
        self.rect = pygame.Rect(x, y, width, height)

class WireModuleInterface(ModuleInterface):
    def __init__(self, wire_module, game_width, game_height):
        super().__init__()

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

        x_offset = 0
        y_interval = game_height // (self.wire_module.num_wires+1)

        for i, wire in enumerate(self.wire_module.wires):
            wire_sprites.append(WireSprite(self.COLOR_MAPPING[wire], x_offset, (i+1) * y_interval, game_width-x_offset*2, 5))
        return wire_sprites

    # def click(self, mouse_pos):
    #     for i, wire_sprite in enumerate(self.wire_sprites):
    #         if wire_sprite.rect.collidepoint(mouse_pos):
    #             # wire_sprite.rgb = (
    #             print("Wire clicked! id: ", i)
    #             self.wire_module.check_defuse(i)

    def render(self, game_surface):
        game_surface.fill((255, 255, 255))
        for wire_sprite in self.wire_sprites:
            pygame.draw.rect(game_surface, wire_sprite.color, wire_sprite.rect)