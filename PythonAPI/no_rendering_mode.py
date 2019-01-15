#!/usr/bin/env python

# Copyright (c) 2017 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

# Allows visualising a 2D map generated by vehicles.

"""
Welcome to CARLA No Rendering Mode Visualizer

    ESC         : quit
"""

# ==============================================================================
# -- find carla module ---------------------------------------------------------
# ==============================================================================

import glob
import os
import sys

try:
    sys.path.append(glob.glob('**/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

# ==============================================================================
# -- imports -------------------------------------------------------------------
# ==============================================================================
import carla

import argparse
import logging
import weakref

try:
    import pygame
    from pygame.locals import K_DOWN
    from pygame.locals import K_LEFT
    from pygame.locals import K_RIGHT
    from pygame.locals import K_UP
    from pygame.locals import K_ESCAPE
except ImportError:
    raise RuntimeError('cannot import pygame, make sure pygame package is installed')

# ==============================================================================
# -- ModuleDefines -------------------------------------------------------------
# ==============================================================================

MODULE_WORLD = 'World'
MODULE_HUD = 'Hud'
MODULE_INPUT = 'Input'

# ==============================================================================
# -- ModuleManager -------------------------------------------------------------
# ==============================================================================


class ModuleManager(object):
    def __init__(self):
        self.modules = []

    def register_module(self, module):
        self.modules.append(module)

    def clear_modules(self):
        del self.modules[:]

    def tick(self, clock):
        # Update all the modules
        for module in self.modules:
            module.tick(clock)

    def render(self, display):
        display.fill((0, 0, 0))
        for module in self.modules:
            module.render(display)

    def get_module(self, name):
        for module in self.modules:
            if module.name == name:
                return module

# ==============================================================================
# -- HUD -----------------------------------------------------------------------
# ==============================================================================


class ModuleHUD (object):

    def __init__(self, name, width, height):
        self.name = name
        self._init_data_params(width, height)
        self._init_hud_params()

    def _init_hud_params(self):
        font = pygame.font.Font(pygame.font.get_default_font(), 20)
        fonts = [x for x in pygame.font.get_fonts() if 'mono' in x]
        default_font = 'ubuntumono'
        mono = default_font if default_font in fonts else fonts[0]
        mono = pygame.font.match_font(mono)
        self._font_mono = pygame.font.Font(mono, 14)

    def _init_data_params(self, height, width):
        self.dim = (height, width)
        self.server_fps = 0
        self.frame_number = 0
        self.simulation_time = 0
        self._show_info = True
        self._info_text = []
        self._server_clock = pygame.time.Clock()

    def on_world_tick(self, timestamp):
        self._server_clock.tick()
        self.server_fps = self._server_clock.get_fps()

    def tick(self, clock):
        if not self._show_info:
            return
        self._info_text = [
            'Server:  % 16d FPS' % self.server_fps,
            'Client:  % 16d FPS' % clock.get_fps()
        ]

    def render(self, display):
        if self._show_info:
            info_surface = pygame.Surface((220, self.dim[1]))
            info_surface.set_alpha(100)
            display.blit(info_surface, (0, 0))
            v_offset = 4
            bar_h_offset = 100
            bar_width = 106
            for item in self._info_text:
                if v_offset + 18 > self.dim[1]:
                    break
                if isinstance(item, list):
                    if len(item) > 1:
                        points = [(x + 8, v_offset + 8 + (1.0 - y) * 30) for x, y in enumerate(item)]
                        pygame.draw.lines(display, (255, 136, 0), False, points, 2)
                    item = None
                    v_offset += 18
                elif isinstance(item, tuple):
                    if isinstance(item[1], bool):
                        rect = pygame.Rect((bar_h_offset, v_offset + 8), (6, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect, 0 if item[1] else 1)
                    else:
                        rect_border = pygame.Rect((bar_h_offset, v_offset + 8), (bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect_border, 1)
                        f = (item[1] - item[2]) / (item[3] - item[2])
                        if item[2] < 0.0:
                            rect = pygame.Rect((bar_h_offset + f * (bar_width - 6), v_offset + 8), (6, 6))
                        else:
                            rect = pygame.Rect((bar_h_offset, v_offset + 8), (f * bar_width, 6))
                        pygame.draw.rect(display, (255, 255, 255), rect)
                    item = item[0]
                if item:  # At this point has to be a str.
                    surface = self._font_mono.render(item, True, (255, 255, 255))
                    display.blit(surface, (8, v_offset))
                v_offset += 18

# ==============================================================================
# -- World ---------------------------------------------------------------------
# ==============================================================================


offset_x = 250
offset_y = 250
scale_x = 1
scale_y = 1


class ModuleWorld(object):
    def __init__(self, name, host, port, timeout, surface):
        self.name = name
        self.surface = surface
        try:
            client = carla.Client(host, port)
            client.set_timeout(timeout)
            self.world = client.get_world()

            weak_self = weakref.ref(self)
            self.world.on_tick(lambda timestamp: ModuleWorld.on_world_tick(weak_self, timestamp))

        except Exception as ex:
            logging.error('Failed connecting to CARLA server')
            exit_game()

    def tick(self, clock):
        pass

    @staticmethod
    def on_world_tick(weak_self, timestamp):
        self = weak_self()
        if not self:
            return
        hud_module = module_manager.get_module(MODULE_HUD)
        hud_module.on_world_tick(timestamp)

    def render_map(self, display, town_map):

        # Get map waypoints
        radius = 2
        width = 1
        thickness = 1
        waypoint_list = town_map.generate_waypoints(10.0)
        point_list = []

        for waypoint in waypoint_list:
            point_list.append((int(waypoint.transform.location.x),
                               int(waypoint.transform.location.y)))

        pygame.draw.lines(self.surface, (255, 0, 255), False, point_list, 1)

    def render_actors(self, display, actors, filter, color):
        filtered_actors = [actor for actor in actors if filter in actor.type_id]
        radius = 2
        width = 1
        for actor in filtered_actors:
            actor_location = actor.get_location()

            pygame.draw.circle(self.surface, color, (int(actor_location.x),
                                                     int(actor_location.y)), radius, width)

    def render(self, display):
        actors = self.world.get_actors()
        town_map = self.world.get_map()
        self.surface.fill((0, 0, 0))
        self.render_map(display, town_map)
        self.render_actors(display, actors, 'vehicle', (255, 0, 0))
        self.render_actors(display, actors, 'traffic_light', (0, 255, 0))
        self.render_actors(display, actors, 'speed_limit', (0, 0, 255))

        result_surface = pygame.transform.scale(self.surface, (int(1280 * scale_x), int(720 * scale_y)))
        display.blit(result_surface, (offset_x, offset_y))

# ==============================================================================
# -- Input -----------------------------------------------------------
# ==============================================================================


class ModuleInput(object):
    def __init__(self, name):
        self.name = name
        self.mouse_pos = (0, 0)

    def render(self, display):
        pass

    def tick(self, clock):
        self.parse_input()

    def _parse_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                exit_game()
            elif event.type == pygame.KEYUP:
                # Quick actions
                if event.key == K_ESCAPE:
                    exit_game()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.mouse_pos = pygame.mouse.get_pos()
                if event.button == 4:
                    # Scale up surface
                    print ("mouse wheel up")
                    global scale_x
                    global scale_y
                    scale_x += 0.1
                    scale_y += 0.1

                if event.button == 5:
                    # Scale down surface
                    global scale_x
                    global scale_y
                    scale_x -= 0.1
                    scale_y -= 0.1

    def _parse_keys(self):
        keys = pygame.key.get_pressed()
        # if keys[pygame.K_LEFT]:
        # Do something

    def _parse_mouse(self):
        if pygame.mouse.get_pressed()[0]:
            x, y = pygame.mouse.get_pos()
            global offset_x
            global offset_y
            offset_x += x - self.mouse_pos[0]
            offset_y += y - self.mouse_pos[1]
            self.mouse_pos = (x, y)

    def parse_input(self):
        self._parse_events()
        self._parse_keys()
        self._parse_mouse()

# ==============================================================================
# -- Game Loop ---------------------------------------------------------------
# ==============================================================================


module_manager = ModuleManager()


def game_loop(args):
    # Init Pygame
    pygame.init()
    display = pygame.display.set_mode(
        (args.width, args.height),
        pygame.HWSURFACE | pygame.DOUBLEBUF)
    pygame.display.set_caption(args.description)

    # Init modules
    input_module = ModuleInput(MODULE_INPUT)
    world_module = ModuleWorld(MODULE_WORLD, args.host, args.port, 2.0,
                               pygame.Surface((args.width, args.height)))
    hud_module = ModuleHUD(MODULE_HUD, args.width, args.height)

    # Register Modules
    module_manager.register_module(input_module)
    module_manager.register_module(hud_module)
    module_manager.register_module(world_module)

    clock = pygame.time.Clock()
    while True:
        clock.tick_busy_loop(60)

        module_manager.tick(clock)
        module_manager.render(display)

        pygame.display.flip()


def exit_game():
    module_manager.clear_modules()
    pygame.quit()
    sys.exit()

# ==============================================================================
# -- Main --------------------------------------------------------------------
# ==============================================================================


def main():
    # Parse arguments
    argparser = argparse.ArgumentParser(
        description='CARLA No Rendering Mode Visualizer')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)'
    )
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')

    args = argparser.parse_args()
    args.description = argparser.description
    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)
    print(__doc__)

    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()
