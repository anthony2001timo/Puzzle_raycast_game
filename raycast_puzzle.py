import pygame
import math
import json
import sys
from typing import List, Tuple, Optional

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60
FOV = math.pi / 3  # 60 degrees field of view
NUM_RAYS = 200
MAX_DEPTH = 20
TILE_SIZE = 64
PLAYER_SPEED = 3
ROTATION_SPEED = 0.05

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
GRAY = (128, 128, 128)
YELLOW = (255, 255, 0)

class Vector2:
    """2D Vector class for position and direction calculations"""
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
    
    def __add__(self, other):
        return Vector2(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other):
        return Vector2(self.x - other.x, self.y - other.y)
    
    def __mul__(self, scalar):
        return Vector2(self.x * scalar, self.y * scalar)
    
    def normalize(self):
        length = math.sqrt(self.x ** 2 + self.y ** 2)
        if length > 0:
            return Vector2(self.x / length, self.y / length)
        return Vector2(0, 0)
    
    def rotate(self, angle):
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        return Vector2(
            self.x * cos_a - self.y * sin_a,
            self.x * sin_a + self.y * cos_a
        )
    
    def dot(self, other):
        return self.x * other.x + self.y * other.y
    
    def length(self):
        return math.sqrt(self.x ** 2 + self.y ** 2)

class Player:
    """Player class handling position, movement, and rotation"""
    def __init__(self, x: float, y: float, angle: float):
        self.position = Vector2(x, y)
        self.angle = angle
        self.direction = Vector2(math.cos(angle), math.sin(angle))
        self.plane = Vector2(-math.sin(angle) * 0.66, math.cos(angle) * 0.66)
    
    def update_direction(self):
        """Update direction vector based on angle"""
        self.direction = Vector2(math.cos(self.angle), math.sin(self.angle))
        self.plane = Vector2(-math.sin(self.angle) * 0.66, math.cos(self.angle) * 0.66)
    
    def move_forward(self, speed: float, level_map):
        """Move player forward with collision detection"""
        new_pos = self.position + self.direction * speed
        if not self._check_collision(new_pos, level_map):
            self.position = new_pos
    
    def move_backward(self, speed: float, level_map):
        """Move player backward with collision detection"""
        new_pos = self.position - self.direction * speed
        if not self._check_collision(new_pos, level_map):
            self.position = new_pos
    
    def rotate(self, angle: float):
        """Rotate player view"""
        self.angle += angle
        self.angle = self.angle % (2 * math.pi)
        self.update_direction()
    
    def _check_collision(self, new_pos: Vector2, level_map) -> bool:
        """Check if new position collides with walls"""
        margin = 0.3
        corners = [
            (new_pos.x - margin, new_pos.y - margin),
            (new_pos.x + margin, new_pos.y - margin),
            (new_pos.x - margin, new_pos.y + margin),
            (new_pos.x + margin, new_pos.y + margin)
        ]
        
        for x, y in corners:
            map_x = int(x)
            map_y = int(y)
            if (map_x < 0 or map_x >= len(level_map.grid[0]) or 
                map_y < 0 or map_y >= len(level_map.grid) or 
                level_map.grid[map_y][map_x] != 0):
                return True
        return False

class LevelMap:
    """Level map class storing the game world"""
    def __init__(self, grid: List[List[int]]):
        self.grid = grid
        self.width = len(grid[0])
        self.height = len(grid)
        self.mirrors = []  # List of mirror positions and orientations
    
    def get_tile(self, x: int, y: int) -> int:
        """Get tile value at given coordinates"""
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return 1  # Return wall for out of bounds
    
    def add_mirror(self, x: int, y: int, orientation: str):
        """Add a mirror to the level"""
        self.mirrors.append({
            'x': x,
            'y': y,
            'orientation': orientation  # 'horizontal' or 'vertical'
        })

class Ray:
    """Ray class for raycasting calculations"""
    def __init__(self, origin: Vector2, direction: Vector2):
        self.origin = origin
        self.direction = direction.normalize()
        self.bounces = 0
        self.max_bounces = 3
    
    def cast(self, level_map: LevelMap, max_distance: float) -> Tuple[float, int, bool]:
        """Cast ray and return distance, wall type, and if it hit a mirror"""
        current_pos = Vector2(self.origin.x, self.origin.y)
        current_dir = Vector2(self.direction.x, self.direction.y)
        total_distance = 0
        
        while self.bounces < self.max_bounces and total_distance < max_distance:
            result = self._cast_single(current_pos, current_dir, level_map, max_distance - total_distance)
            distance, wall_type, hit_mirror, mirror_data = result
            
            total_distance += distance
            
            if hit_mirror and mirror_data:
                # Calculate reflection
                current_pos = Vector2(
                    current_pos.x + current_dir.x * distance,
                    current_pos.y + current_dir.y * distance
                )
                
                # Reflect direction based on mirror orientation
                if mirror_data['orientation'] == 'horizontal':
                    current_dir.y = -current_dir.y
                else:  # vertical
                    current_dir.x = -current_dir.x
                
                self.bounces += 1
            else:
                return total_distance, wall_type, False
        
        return total_distance, wall_type, False
    
    def _cast_single(self, origin: Vector2, direction: Vector2, level_map: LevelMap, max_distance: float):
        """Cast a single ray segment"""
        # DDA algorithm for raycasting
        if abs(direction.x) < 0.0001:
            direction.x = 0.0001
        if abs(direction.y) < 0.0001:
            direction.y = 0.0001
        
        ray_cos = direction.x
        ray_sin = direction.y
        
        # Calculate step sizes
        step_x = 1 if ray_cos > 0 else -1
        step_y = 1 if ray_sin > 0 else -1
        
        # Calculate initial distances
        if ray_cos > 0:
            h_x = math.floor(origin.x) + 1
            h_dx = 1
        else:
            h_x = math.ceil(origin.x) - 1
            h_dx = -1
        
        if ray_sin > 0:
            v_y = math.floor(origin.y) + 1
            v_dy = 1
        else:
            v_y = math.ceil(origin.y) - 1
            v_dy = -1
        
        # Cast ray
        distance = 0
        while distance < max_distance:
            # Check horizontal intersections
            h_dist = (h_x - origin.x) / ray_cos
            h_y = origin.y + h_dist * ray_sin
            
            # Check vertical intersections
            v_dist = (v_y - origin.y) / ray_sin
            v_x = origin.x + v_dist * ray_cos
            
            # Choose closer intersection
            if abs(h_dist) < abs(v_dist):
                distance = abs(h_dist)
                hit_x = h_x
                hit_y = h_y
                
                # Check for wall or mirror
                check_x = int(h_x - (0.5 if ray_cos < 0 else -0.5))
                check_y = int(h_y)
                
                if check_x < 0 or check_x >= level_map.width or check_y < 0 or check_y >= level_map.height:
                    return distance, 1, False, None
                
                tile = level_map.grid[check_y][check_x]
                if tile != 0:
                    # Check if it's a mirror
                    for mirror in level_map.mirrors:
                        if mirror['x'] == check_x and mirror['y'] == check_y:
                            return distance, tile, True, mirror
                    return distance, tile, False, None
                
                h_x += h_dx
            else:
                distance = abs(v_dist)
                hit_x = v_x
                hit_y = v_y
                
                # Check for wall or mirror
                check_x = int(v_x)
                check_y = int(v_y - (0.5 if ray_sin < 0 else -0.5))
                
                if check_x < 0 or check_x >= level_map.width or check_y < 0 or check_y >= level_map.height:
                    return distance, 1, False, None
                
                tile = level_map.grid[check_y][check_x]
                if tile != 0:
                    # Check if it's a mirror
                    for mirror in level_map.mirrors:
                        if mirror['x'] == check_x and mirror['y'] == check_y:
                            return distance, tile, True, mirror
                    return distance, tile, False, None
                
                v_y += v_dy
        
        return max_distance, 0, False, None

class Renderer:
    """Renderer class handling all drawing operations"""
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.width = screen.get_width()
        self.height = screen.get_height()
    
    def render_3d_view(self, player: Player, level_map: LevelMap):
        """Render the 3D view using raycasting"""
        # Clear screen
        self.screen.fill(BLACK)
        
        # Draw ceiling and floor
        pygame.draw.rect(self.screen, (50, 50, 50), (0, 0, self.width, self.height // 2))
        pygame.draw.rect(self.screen, (100, 100, 100), (0, self.height // 2, self.width, self.height // 2))
        
        # Cast rays
        for x in range(NUM_RAYS):
            # Calculate ray direction
            camera_x = 2 * x / NUM_RAYS - 1
            ray_dir = player.direction + player.plane * camera_x
            
            # Create and cast ray
            ray = Ray(player.position, ray_dir)
            distance, wall_type, hit_mirror = ray.cast(level_map, MAX_DEPTH)
            
            # Fix fisheye effect
            distance = distance * abs(ray_dir.normalize().dot(player.direction))
            
            # Calculate wall height
            if distance > 0:
                wall_height = min(int(self.height / distance), self.height)
            else:
                wall_height = self.height
            
            # Calculate wall position
            draw_start = (self.height - wall_height) // 2
            draw_end = (self.height + wall_height) // 2
            
            # Calculate color based on distance and wall type
            shade = max(0, min(255, int(255 / (1 + distance * 0.2))))
            
            if wall_type == 1:  # Regular wall
                color = (shade, shade, shade)
            elif wall_type == 2:  # Different wall type
                color = (shade, 0, 0)
            elif wall_type == 3:  # Mirror
                color = (0, shade, shade)
            else:
                color = (0, shade, 0)
            
            # Draw vertical line
            x_pos = int(x * self.width / NUM_RAYS)
            width = max(1, int(self.width / NUM_RAYS))
            pygame.draw.rect(self.screen, color, (x_pos, draw_start, width, wall_height))
    
    def render_minimap(self, player: Player, level_map: LevelMap):
        """Render a minimap in the corner"""
        minimap_size = 150
        minimap_x = self.width - minimap_size - 10
        minimap_y = 10
        tile_size = minimap_size // max(level_map.width, level_map.height)
        
        # Draw minimap background
        pygame.draw.rect(self.screen, BLACK, (minimap_x, minimap_y, minimap_size, minimap_size))
        
        # Draw tiles
        for y in range(level_map.height):
            for x in range(level_map.width):
                tile = level_map.grid[y][x]
                if tile == 1:
                    color = WHITE
                elif tile == 2:
                    color = RED
                elif tile == 3:
                    color = BLUE
                else:
                    color = GRAY
                
                pygame.draw.rect(self.screen, color, 
                               (minimap_x + x * tile_size, 
                                minimap_y + y * tile_size, 
                                tile_size - 1, tile_size - 1))
        
        # Draw player
        player_minimap_x = minimap_x + int(player.position.x * tile_size)
        player_minimap_y = minimap_y + int(player.position.y * tile_size)
        pygame.draw.circle(self.screen, YELLOW, (player_minimap_x, player_minimap_y), 3)
        
        # Draw player direction
        dir_end_x = player_minimap_x + int(player.direction.x * 10)
        dir_end_y = player_minimap_y + int(player.direction.y * 10)
        pygame.draw.line(self.screen, YELLOW, (player_minimap_x, player_minimap_y), 
                        (dir_end_x, dir_end_y), 2)

class Game:
    """Main game class"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Raycast Puzzle Game")
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Load level
        self.level_map = self.load_level("level.json")
        
        # Initialize player
        self.player = Player(1.5, 1.5, 0)
        
        # Initialize renderer
        self.renderer = Renderer(self.screen)
    
    def load_level(self, filename: str) -> LevelMap:
        """Load level from JSON file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            level_map = LevelMap(data['grid'])
            
            # Load mirrors
            if 'mirrors' in data:
                for mirror in data['mirrors']:
                    level_map.add_mirror(mirror['x'], mirror['y'], mirror['orientation'])
            
            # Load player position if specified
            if 'player' in data:
                self.player = Player(data['player']['x'], data['player']['y'], data['player']['angle'])
            
            return level_map
        except FileNotFoundError:
            # Create default level if file not found
            default_grid = [
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 1, 3, 1, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 1, 2, 1, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 0, 0, 0, 0, 0, 0, 0, 0, 1],
                [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
            ]
            level_map = LevelMap(default_grid)
            level_map.add_mirror(4, 3, 'vertical')
            return level_map
    
    def handle_input(self):
        """Handle keyboard input"""
        keys = pygame.key.get_pressed()
        
        # Movement
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.player.move_forward(PLAYER_SPEED / FPS, self.level_map)
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.player.move_backward(PLAYER_SPEED / FPS, self.level_map)
        
        # Rotation
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.player.rotate(-ROTATION_SPEED)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.player.rotate(ROTATION_SPEED)
    
    def run(self):
        """Main game loop"""
        while self.running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
            
            # Handle input
            self.handle_input()
            
            # Render
            self.renderer.render_3d_view(self.player, self.level_map)
            self.renderer.render_minimap(self.player, self.level_map)
            
            # Show FPS
            fps_text = pygame.font.Font(None, 36).render(f"FPS: {int(self.clock.get_fps())}", True, WHITE)
            self.screen.blit(fps_text, (10, 10))
            
            # Update display
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

# Create default level.json file if it doesn't exist
def create_default_level_file():
    """Create a default level.json file"""
    level_data = {
        "grid": [
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 1, 3, 1, 0, 0, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 1],
            [1, 0, 0, 2, 0, 0, 0, 0, 1, 0, 0, 1],
            [1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 2, 0, 0, 1, 3, 1, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1],
            [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
        ],
        "mirrors": [
            {"x": 4, "y": 3, "orientation": "vertical"},
            {"x": 8, "y": 5, "orientation": "horizontal"},
            {"x": 7, "y": 8, "orientation": "vertical"}
        ],
        "player": {
            "x": 1.5,
            "y": 1.5,
            "angle": 0
        }
    }
    
    try:
        with open("level.json", "w") as f:
            json.dump(level_data, f, indent=4)
        print("Created level.json file")
    except Exception as e:
        print(f"Could not create level.json: {e}")

if __name__ == "__main__":
    # Create default level file if it doesn't exist
    import os
    if not os.path.exists("level.json"):
        create_default_level_file()
    
    # Run the game
    game = Game()
    game.run()
