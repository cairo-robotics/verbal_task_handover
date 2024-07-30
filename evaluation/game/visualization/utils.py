import pygame
from pygame.locals import DOUBLEBUF, HWSURFACE, QUIT, RESIZABLE, VIDEORESIZE
import json


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

class MultiFramePygameImage:
    def __init__(self, img_path, frames_path):
        self.image = pygame.image.load(img_path).convert_alpha()
        self.frames_rectangles = self.load_frames_rectangles(frames_path)
    
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

    # def sprite(self, frame_name):
        # return self.image.subsurface(self.frames_rectangles[frame_name])

    def load_frames_rectangles(self, json_path):
        with open(json_path, "r") as f:
            frames = json.load(f)
        
        sprite_width, sprite_height = frames["sprite size"]
        sheet_width, sheet_height = frames["sheet size"]

        self.sprite_size = (sprite_width, sprite_height)

        result = {}
        frame_start = [0, 0]
        for i, frame_id in enumerate(frames["frames"]):
            frame_start[0] = (i % sheet_width) * sprite_width
            frame_start[1] = (i // sheet_width) * sprite_height
            
            frame_name = frame_id + ".png"
            result[frame_name] = pygame.Rect(
                frame_start[0], frame_start[1], sprite_width, sprite_height
            )

        return result
