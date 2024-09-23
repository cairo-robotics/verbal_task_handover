import pygame
from pygame.locals import DOUBLEBUF, HWSURFACE, QUIT, RESIZABLE, VIDEORESIZE
import json

def run_static_resizeable_window(surface, fps=30):
    """
    window that can be resized and closed using gui
    """
    pygame.init()
    clock = pygame.time.Clock()
    window = pygame.display.set_mode(
        surface.get_size(), HWSURFACE | DOUBLEBUF | RESIZABLE
    )
    window.blit(surface, (0, 0))
    pygame.display.flip()
    try:
        while True:
            pygame.event.pump()
            event = pygame.event.wait()
            if event.type == QUIT:
                pygame.display.quit()
                pygame.quit()
            elif event.type == VIDEORESIZE:
                window = pygame.display.set_mode(
                    event.dict["size"], HWSURFACE | DOUBLEBUF | RESIZABLE
                )
                window.blit(
                    pygame.transform.scale(surface, event.dict["size"]), (0, 0)
                )
                pygame.display.flip()
                clock.tick(fps)
    except:
        pygame.display.quit()
        pygame.quit()
        if event.type != QUIT:  # if user meant to quit error does not matter
            raise


def scale_surface_by_factor(surface, scale_by_factor):
    """return scaled input surfacem (with size multiplied by scale_by_factor param)
    scales also content of the surface
    """
    unscaled_size = surface.get_size()
    scaled_size = tuple(int(dim * scale_by_factor) for dim in unscaled_size)
    return pygame.transform.scale(surface, scaled_size)

def blit_on_new_surface_of_size(surface, size, background_color=None):
    """blit surface on new surface of given size of surface (with no resize of its content), filling not covered parts of result area with background color"""
    result_surface = pygame.surface.Surface(size)
    if background_color:
        result_surface.fill(background_color)
    result_surface.blit(surface, (0, 0))
    return result_surface

def get_scaled_surface_size(pygame_image, new_size):
    return (new_size[0] * pygame_image.sprite_scaling, new_size[1] * pygame_image.sprite_scaling)

def scale_to_width(pygame_image, new_width):
    """return scaled input surface to have width equal to new_width, keeping aspect ratio"""
    width, height = pygame_image.image.get_size()
    scale_factor = new_width / width
    return pygame.transform.scale(pygame_image.image, (new_width, int(height * scale_factor)))

class SingleFramePygameImage:
    def __init__(self, img_path, scaling=1.0):
        self.image = pygame.image.load(img_path).convert_alpha()
        self.sprite_scaling = scaling

    def blit_on_surface_scaled(
        self, surface, top_left_pixel_position, new_size
    ):
        scaled_surface = pygame.transform.scale(
            self.image, (new_size[0] * self.sprite_scaling, new_size[1] * self.sprite_scaling)
        )
        surface.blit(scaled_surface, top_left_pixel_position)

class MultiFramePygameImage:
    def __init__(self, img_path, frames_path, scaling=1.0):
        self.mapping = None
        self.image = pygame.image.load(img_path).convert_alpha()
        self.frames_rectangles = self.load_frames_rectangles(frames_path)
        self.extra_sprites = {}
        self.sprite_scaling = scaling
        self.layer = False
        self.auto_tile = False
    
    def add_extra_sprite(self, sprite_name, img_path):
        self.extra_sprites[sprite_name] = pygame.image.load(img_path).convert_alpha()

    def blit_on_surface(
        self, surface, top_left_pixel_position, frame_name, **kwargs
    ):
        # print(self.frames_rectangles)
        surface.blit(
            self.image,
            top_left_pixel_position,
            area=self.frames_rectangles[frame_name],
            **kwargs
        )

    def sprite(self, frame_name):
        if frame_name in self.extra_sprites:
            return self.extra_sprites[frame_name]
        return self.image.subsurface(self.frames_rectangles[frame_name])
    
    def _blit_on_surface_scaled(
        self, surface, top_left_pixel_position, frame_name, new_size
        ):

        sprite_surface = self.sprite(frame_name)
        scaled_surface = pygame.transform.scale(sprite_surface, (new_size[0] * self.sprite_scaling, new_size[1] * self.sprite_scaling))
        surface.blit(scaled_surface, top_left_pixel_position)

    def blit_on_surface_scaled(
        self, surface, top_left_pixel_position, frame_name, new_size
        ):

        if self.layer:
            self._blit_on_surface_scaled(surface, top_left_pixel_position, "base.png", new_size)
        self._blit_on_surface_scaled(surface, top_left_pixel_position, frame_name, new_size)

    def load_frames_rectangles(self, json_path):
        with open(json_path, "r") as f:
            frames = json.load(f)
        
        sprite_width, sprite_height = frames["sprite size"]
        sheet_width, sheet_height = frames["sheet size"]

        self.sprite_size = (sprite_width, sprite_height)

        result = {}

        if "sheet start" in frames:
            sheet_start = frames["sheet start"]
        else: 
            sheet_start = [0, 0]
        frame_start = sheet_start.copy()
        for i, frame_id in enumerate(frames["frames"]):
            frame_start[0] = (sheet_start[0] + i % sheet_width) * sprite_width
            frame_start[1] = (sheet_start[1] + i // sheet_width) * sprite_height
            
            frame_name = frame_id + ".png"
            result[frame_name] = pygame.Rect(
                frame_start[0], frame_start[1], sprite_width, sprite_height
            )

        if "mapping" in frames:
            self.mapping = frames["mapping"]

        return result
