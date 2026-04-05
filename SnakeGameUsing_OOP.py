import pygame
import random
import json
import os
import math
from abc import ABC, abstractmethod
from enum import Enum

# Configuration

WIDTH, HEIGHT = 900, 660
GRID_SIZE = 20
COLS = WIDTH // GRID_SIZE
ROWS = HEIGHT // GRID_SIZE
FPS = 7
BASE_SPEED = 7

# Colour palette
BLACK       = (10,  10,  15)
WHITE       = (230, 230, 230)
DARK_GRAY   = (25,  25,  35)
GRID_COLOR  = (30,  30,  42)
GREEN_HEAD  = (80,  220, 120)
GREEN_BODY  = (50,  180,  90)
GREEN_TAIL  = (30,  130,  60)
FOOD_COLOR  = (255,  80,  80)
FOOD_GLOW   = (255, 160, 120)
GOLD        = (255, 210,  50)
BLUE_ACCENT = ( 80, 160, 255)
PURPLE      = (160,  80, 255)
UI_BG       = (18,  18,  28)
PANEL_BG    = (22,  22,  34)

SCORE_FILE = "highscores.json"

# Enums

class Direction(Enum):
    UP    = (0,  -1)
    DOWN  = (0,   1)
    LEFT  = (-1,  0)
    RIGHT = (1,   0)

class GameState(Enum):
    MENU       = "menu"
    PLAYING    = "playing"
    PAUSED     = "paused"
    GAME_OVER  = "game_over"

class FoodType(Enum):
    NORMAL  = "normal"   # +1 point
    BONUS   = "bonus"    # +3 points, appears briefly
    GOLDEN  = "golden"   # +5 points, rare

# High Score Manager 

class HighScoreManager:
    """Handles persistent high score storage using JSON."""

    def __init__(self, filepath: str = SCORE_FILE):
        self.filepath = filepath
        self.scores: list[int] = self._load()

    def _load(self) -> list[int]:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    data = json.load(f)
                    return sorted(data.get("scores", []), reverse=True)[:10]
            except (json.JSONDecodeError, KeyError):
                return []
        return []

    def save(self, score: int) -> bool:
        """Returns True if new high score."""
        is_high = not self.scores or score > self.scores[0]
        self.scores.append(score)
        self.scores = sorted(self.scores, reverse=True)[:10]
        with open(self.filepath, "w") as f:
            json.dump({"scores": self.scores}, f)
        return is_high

    @property
    def best(self) -> int:
        return self.scores[0] if self.scores else 0

# Particle System 

class Particle:
    def __init__(self, x: int, y: int, color: tuple):
        self.x = float(x)
        self.y = float(y)
        self.color = color
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(2, 7)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = 1.0
        self.decay = random.uniform(0.04, 0.09)
        self.size = random.randint(3, 7)

    def update(self):
        self.x  += self.vx
        self.y  += self.vy
        self.vy += 0.2          # gravity
        self.life -= self.decay
        self.size = max(1, self.size - 0.15)

    def draw(self, surface: pygame.Surface):
        alpha = int(self.life * 255)
        r, g, b = self.color
        color = (min(255, r), min(255, g), min(255, b))
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), int(self.size))

    @property
    def alive(self) -> bool:
        return self.life > 0

class ParticleSystem:
    def __init__(self):
        self.particles: list[Particle] = []

    def emit(self, x: int, y: int, color: tuple, count: int = 12):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def update(self):
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update()

    def draw(self, surface: pygame.Surface):
        for p in self.particles:
            p.draw(surface)

# Abstract Game Object 

class GameObject(ABC):
    @abstractmethod
    def draw(self, surface: pygame.Surface): pass

    @abstractmethod
    def update(self): pass

# Food 

class Food(GameObject):
    CONFIGS = {
        FoodType.NORMAL: {"color": FOOD_COLOR,  "points": 1, "lifetime": None, "symbol": "●"},
        FoodType.BONUS:  {"color": BLUE_ACCENT, "points": 3, "lifetime": 60,  "symbol": "★"},
        FoodType.GOLDEN: {"color": GOLD,        "points": 5, "lifetime": 40,  "symbol": "◆"},
    }

    def __init__(self, food_type: FoodType, occupied: list):
        self.food_type = food_type
        cfg = self.CONFIGS[food_type]
        self.color    = cfg["color"]
        self.points   = cfg["points"]
        self.lifetime = cfg["lifetime"]
        self.symbol   = cfg["symbol"]
        self.age      = 0
        self.pulse    = 0.0
        self.position = self._random_pos(occupied)

    def _random_pos(self, occupied: list) -> tuple:
        while True:
            pos = (random.randint(1, COLS - 2), random.randint(3, ROWS - 2))
            if pos not in occupied:
                return pos

    def update(self):
        self.age   += 1
        self.pulse  = math.sin(self.age * 0.15) * 3

    def draw(self, surface: pygame.Surface):
        x = self.position[0] * GRID_SIZE + GRID_SIZE // 2
        y = self.position[1] * GRID_SIZE + GRID_SIZE // 2
        r = GRID_SIZE // 2 + int(self.pulse)

        # Glow effect
        for i in range(4, 0, -1):
            alpha_surf = pygame.Surface((r * 2 + i * 4, r * 2 + i * 4), pygame.SRCALPHA)
            glow_a = max(0, 40 - i * 8)
            pygame.draw.circle(alpha_surf, (*self.color, glow_a),
                               (r + i * 2, r + i * 2), r + i * 2)
            surface.blit(alpha_surf, (x - r - i * 2, y - r - i * 2))

        pygame.draw.circle(surface, self.color, (x, y), r)
        pygame.draw.circle(surface, WHITE,      (x, y), r, 1)

    @property
    def expired(self) -> bool:
        return self.lifetime is not None and self.age >= self.lifetime

# Snake 

class Snake(GameObject):
    def __init__(self):
        start = (COLS // 2, ROWS // 2)
        self.body: list[tuple] = [start, (start[0]-1, start[1]), (start[0]-2, start[1])]
        self.direction  = Direction.RIGHT
        self._next_dir  = Direction.RIGHT
        self.grew       = False
        self.alive      = True
        self.move_timer = 0

    def set_direction(self, new_dir: Direction):
        opposites = {
            Direction.UP: Direction.DOWN, Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT, Direction.RIGHT: Direction.LEFT,
        }
        if new_dir != opposites.get(self.direction):
            self._next_dir = new_dir

    def update(self):
        if not self.alive:
            return
        self.direction = self._next_dir
        dx, dy = self.direction.value
        head   = self.body[0]
        new_head = (head[0] + dx, head[1] + dy)

        # Wall collision
        if not (0 <= new_head[0] < COLS and 1 <= new_head[1] < ROWS):
            self.alive = False
            return

        # Self collision
        if new_head in self.body[:-1]:
            self.alive = False
            return

        self.body.insert(0, new_head)
        if not self.grew:
            self.body.pop()
        self.grew = False

    def grow(self):
        self.grew = True

    def draw(self, surface: pygame.Surface):
        total = len(self.body)
        for i, (gx, gy) in enumerate(self.body):
            x = gx * GRID_SIZE
            y = gy * GRID_SIZE
            rect = pygame.Rect(x + 1, y + 1, GRID_SIZE - 2, GRID_SIZE - 2)

            if i == 0:
                color = GREEN_HEAD
                radius = 6
            elif i == total - 1:
                color = GREEN_TAIL
                radius = 3
            else:
                t = i / max(total - 1, 1)
                color = (
                    int(GREEN_BODY[0] + (GREEN_TAIL[0] - GREEN_BODY[0]) * t),
                    int(GREEN_BODY[1] + (GREEN_TAIL[1] - GREEN_BODY[1]) * t),
                    int(GREEN_BODY[2] + (GREEN_TAIL[2] - GREEN_BODY[2]) * t),
                )
                radius = 4

            pygame.draw.rect(surface, color, rect, border_radius=radius)

            # Eyes on head
            if i == 0:
                self._draw_eyes(surface, gx, gy)

    def _draw_eyes(self, surface, gx, gy):
        cx = gx * GRID_SIZE + GRID_SIZE // 2
        cy = gy * GRID_SIZE + GRID_SIZE // 2
        dx, dy = self.direction.value
        perp = (-dy, dx)
        for sign in (1, -1):
            ex = cx + dx * 4 + perp[0] * sign * 4
            ey = cy + dy * 4 + perp[1] * sign * 4
            pygame.draw.circle(surface, WHITE, (ex, ey), 3)
            pygame.draw.circle(surface, BLACK, (ex + dx, ey + dy), 1)

    @property
    def head(self):
        return self.body[0]

# Game Manager (Singleton) 

class GameManager:
    _instance = None

    @staticmethod
    def get_instance():
        if GameManager._instance is None:
            GameManager()
        return GameManager._instance

    def __init__(self):
        if GameManager._instance is not None:
            raise Exception("Singleton — use get_instance()")
        GameManager._instance = self
        self.hs_manager  = HighScoreManager()
        self.particles   = ParticleSystem()
        self.state       = GameState.MENU
        self.score       = 0
        self.level       = 1
        self.snake: Snake | None = None
        self.foods: list[Food]   = []
        self.speed       = FPS
        self.combo       = 0
        self.new_high    = False
        self._bonus_timer = 0

    def start_game(self):
        self.score       = 0
        self.level       = 1
        self.combo       = 0
        self.speed       = BASE_SPEED
        self.new_high    = False
        self._bonus_timer = 0
        self.snake  = Snake()
        self.foods  = [Food(FoodType.NORMAL, [])]
        self.state  = GameState.PLAYING

    def _occupied(self) -> list:
        occ = list(self.snake.body)
        occ += [f.position for f in self.foods]
        return occ

    def update(self):
        if self.state != GameState.PLAYING:
            return

        self.snake.update()
        self.particles.update()

        if not self.snake.alive:
            self.new_high = self.hs_manager.save(self.score)
            self.state = GameState.GAME_OVER
            # Death burst
            hx = self.snake.head[0] * GRID_SIZE + GRID_SIZE // 2
            hy = self.snake.head[1] * GRID_SIZE + GRID_SIZE // 2
            self.particles.emit(hx, hy, FOOD_COLOR, 30)
            return

        # Food logic
        for food in self.foods[:]:
            food.update()
            if food.position == self.snake.head:
                pts = food.points * self.combo if self.combo > 1 else food.points
                self.score += pts
                self.combo += 1
                self.snake.grow()
                fx = food.position[0] * GRID_SIZE + GRID_SIZE // 2
                fy = food.position[1] * GRID_SIZE + GRID_SIZE // 2
                self.particles.emit(fx, fy, food.color, 15)
                eaten_type = food.food_type
                self.foods.remove(food)
                # Only spawn a new red food when the red one was eaten
                if eaten_type == FoodType.NORMAL:
                    self.foods.append(Food(FoodType.NORMAL, self._occupied()))
                self._level_up()
            elif food.expired:
                self.foods.remove(food)
                self.combo = 0
                # If red food somehow expired, replace it
                if food.food_type == FoodType.NORMAL:
                    self.foods.append(Food(FoodType.NORMAL, self._occupied()))

        # Spawn bonus food every 60 game ticks (~8 seconds at speed 7)
        self._bonus_timer += 1
        if self._bonus_timer >= 60:
            self._bonus_timer = 0
            ftype = FoodType.GOLDEN if random.random() < 0.25 else FoodType.BONUS
            if not any(f.food_type == ftype for f in self.foods):
                self.foods.append(Food(ftype, self._occupied()))

    def _level_up(self):
        new_level = 1 + self.score // 5
        if new_level > self.level:
            self.level = new_level
            # Speed stays fixed — only level counter increases
            # Uncomment below if you want speed to increase with level:
            # self.speed = min(BASE_SPEED + (self.level - 1), 20)

# Renderer 

class Renderer:
    def __init__(self, surface: pygame.Surface):
        self.surface = surface
        pygame.font.init()
        self.font_large  = pygame.font.SysFont("consolas", 52, bold=True)
        self.font_medium = pygame.font.SysFont("consolas", 28, bold=True)
        self.font_small  = pygame.font.SysFont("consolas", 18)
        self.font_tiny   = pygame.font.SysFont("consolas", 14)

    def _text(self, text, font, color, x, y, center=True):
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(x, y)) if center else surf.get_rect(topleft=(x, y))
        self.surface.blit(surf, rect)
        return rect

    def draw_grid(self):
        for x in range(0, WIDTH, GRID_SIZE):
            pygame.draw.line(self.surface, GRID_COLOR, (x, GRID_SIZE * 2), (x, HEIGHT))
        for y in range(GRID_SIZE * 2, HEIGHT, GRID_SIZE):
            pygame.draw.line(self.surface, GRID_COLOR, (0, y), (WIDTH, y))

    def draw_hud(self, manager: GameManager):
        # HUD bar
        pygame.draw.rect(self.surface, UI_BG, (0, 0, WIDTH, GRID_SIZE * 2))
        pygame.draw.line(self.surface, GREEN_BODY, (0, GRID_SIZE * 2), (WIDTH, GRID_SIZE * 2), 1)

        self._text(f"SCORE  {manager.score:05d}", self.font_small, GREEN_HEAD, 120, GRID_SIZE, center=True)
        self._text(f"BEST   {manager.hs_manager.best:05d}", self.font_small, GOLD, 320, GRID_SIZE, center=True)
        self._text(f"LEVEL  {manager.level:02d}", self.font_small, BLUE_ACCENT, 520, GRID_SIZE, center=True)

        if manager.combo > 1:
            self._text(f"COMBO x{manager.combo}", self.font_small, PURPLE, 720, GRID_SIZE, center=True)

        # Food legend
        legend_x = WIDTH - 160
        self._text("★ +3  ◆ +5", self.font_tiny, (150, 150, 180), legend_x, GRID_SIZE, center=True)

    def draw_menu(self, manager: GameManager):
        self.surface.fill(BLACK)
        self.draw_grid()

        self._text("~~ SNAKE GAME ~~", self.font_large, GREEN_HEAD, WIDTH // 2, 180)
        self._text("ARE  YOU  READY?", self.font_small, GREEN_BODY, WIDTH // 2, 240)

        pygame.draw.rect(self.surface, PANEL_BG, (WIDTH//2 - 220, 280, 440, 260), border_radius=12)
        pygame.draw.rect(self.surface, GREEN_BODY, (WIDTH//2 - 220, 280, 440, 260), 1, border_radius=12)

        lines = [
            ("ARROW KEYS  /  WASD", WHITE,       330),
            ("Move the snake",       (130,130,150), 358),
            ("P  →  Pause",          WHITE,       395),
            ("R  →  Restart",        WHITE,       423),
            ("ESC  →  Quit",         WHITE,       451),
            ("★ Bonus  ◆ Golden",   GOLD,        490),
            ("Eat fast for combos!", PURPLE,      518),
        ]
        for txt, col, y in lines:
            self._text(txt, self.font_small if y < 470 else self.font_tiny, col, WIDTH//2, y)

        if manager.hs_manager.best:
            self._text(f"Best Score: {manager.hs_manager.best}", self.font_small, GOLD, WIDTH//2, 570)

        pulse = abs(math.sin(pygame.time.get_ticks() * 0.003))
        col = (int(80 + pulse * 150), int(220 + pulse * 35), int(120 + pulse * 50))
        self._text("Press  SPACE  to play", self.font_medium, col, WIDTH//2, 630)

    def draw_game(self, manager: GameManager):
        self.surface.fill(BLACK)
        self.draw_grid()
        self.draw_hud(manager)
        for food in manager.foods:
            food.draw(self.surface)
        if manager.snake:
            manager.snake.draw(self.surface)
        manager.particles.draw(self.surface)

    def draw_paused(self, manager: GameManager):
        self.draw_game(manager)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.surface.blit(overlay, (0, 0))
        self._text("PAUSED", self.font_large,  WHITE, WIDTH//2, HEIGHT//2 - 30)
        self._text("Press P to resume", self.font_small, (180,180,180), WIDTH//2, HEIGHT//2 + 40)

    def draw_game_over(self, manager: GameManager):
        self.draw_game(manager)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.surface.blit(overlay, (0, 0))

        self._text("GAME  OVER", self.font_large, FOOD_COLOR, WIDTH//2, HEIGHT//2 - 100)
        self._text(f"Score: {manager.score}", self.font_medium, WHITE, WIDTH//2, HEIGHT//2 - 30)

        if manager.new_high:
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.005))
            col = (int(200 + pulse*55), int(180 + pulse*30), 50)
            self._text("★  NEW HIGH SCORE  ★", self.font_medium, col, WIDTH//2, HEIGHT//2 + 20)

        self._text(f"Best: {manager.hs_manager.best}", self.font_small, GOLD, WIDTH//2, HEIGHT//2 + 65)

        if manager.hs_manager.scores:
            self._text("Top Scores", self.font_small, (160,160,200), WIDTH//2, HEIGHT//2 + 110)
            for i, s in enumerate(manager.hs_manager.scores[:5]):
                col = GOLD if i == 0 else (180, 180, 180)
                self._text(f"#{i+1}  {s:05d}", self.font_tiny, col, WIDTH//2, HEIGHT//2 + 135 + i * 20)

        pulse = abs(math.sin(pygame.time.get_ticks() * 0.004))
        col = (int(80 + pulse*150), int(220 + pulse*35), int(120 + pulse*50))
        self._text("R — Restart     ESC — Menu", self.font_small, col, WIDTH//2, HEIGHT - 40)

# Main 

def main():
    pygame.init()
    screen  = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Snake — Professional Edition")

    clock    = pygame.time.Clock()
    manager  = GameManager.get_instance()
    renderer = Renderer(screen)

    DIR_MAP = {
        pygame.K_UP:    Direction.UP,    pygame.K_w: Direction.UP,
        pygame.K_DOWN:  Direction.DOWN,  pygame.K_s: Direction.DOWN,
        pygame.K_LEFT:  Direction.LEFT,  pygame.K_a: Direction.LEFT,
        pygame.K_RIGHT: Direction.RIGHT, pygame.K_d: Direction.RIGHT,
    }

    move_accumulator = 0.0

    running = True
    while running:
        dt = clock.tick(60)           # fixed 60 fps render loop

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if manager.state == GameState.PLAYING:
                        manager.state = GameState.MENU
                    else:
                        running = False

                elif event.key == pygame.K_SPACE and manager.state == GameState.MENU:
                    manager.start_game()

                elif event.key == pygame.K_r:
                    if manager.state in (GameState.GAME_OVER, GameState.PLAYING):
                        manager.start_game()

                elif event.key == pygame.K_p and manager.state == GameState.PLAYING:
                    manager.state = GameState.PAUSED

                elif event.key == pygame.K_p and manager.state == GameState.PAUSED:
                    manager.state = GameState.PLAYING

                elif manager.state == GameState.PLAYING and manager.snake:
                    if event.key in DIR_MAP:
                        manager.snake.set_direction(DIR_MAP[event.key])

        # Game logic runs at `speed` ticks/sec, rendering always at 60fps
        if manager.state == GameState.PLAYING:
            move_accumulator += dt
            interval = 1000 / manager.speed
            while move_accumulator >= interval:
                manager.update()
                move_accumulator -= interval
        else:
            manager.particles.update()

        # Draw
        if manager.state == GameState.MENU:
            renderer.draw_menu(manager)
        elif manager.state == GameState.PLAYING:
            renderer.draw_game(manager)
        elif manager.state == GameState.PAUSED:
            renderer.draw_paused(manager)
        elif manager.state == GameState.GAME_OVER:
            renderer.draw_game_over(manager)

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()