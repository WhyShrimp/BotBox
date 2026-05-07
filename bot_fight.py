#!/usr/bin/env python3
"""
Бот-файтинг на круглой арене.
Два бота сражаются: можно снять ХП или вытолкнуть за круг.
Есть действия: движение, атака, защита (с вариациями).
Тактика ботов настраивается через веса действий и условия.
Запуск: python bot_fight.py
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Callable, Optional, Tuple


class ActionType(Enum):
    MOVE = auto()
    ATTACK = auto()
    BLOCK = auto()
    DASH = auto()      # рывок (усиленное движение)
    HEAVY_ATTACK = auto()  # тяжелая атака (медленнее, сильнее)
    COUNTER = auto()   # контратака (защита + ответный удар)


@dataclass
class BotConfig:
    name: str
    max_hp: int = 100
    speed: float = 1.0
    attack_power: float = 10.0
    defense_power: float = 5.0
    radius: float = 2.0
    # Веса действий (чем больше вес, тем чаще выбирается)
    action_weights: Dict[ActionType, float] = field(default_factory=lambda: {
        ActionType.MOVE: 3.0,
        ActionType.ATTACK: 4.0,
        ActionType.BLOCK: 2.0,
        ActionType.DASH: 1.0,
        ActionType.HEAVY_ATTACK: 1.5,
        ActionType.COUNTER: 1.0,
    })
    # Условия для изменения тактики (hp_threshold -> новые веса)
    tactic_conditions: Dict[float, Dict[ActionType, float]] = field(default_factory=dict)


@dataclass
class Bot:
    config: BotConfig
    x: float = 0.0
    y: float = 0.0
    hp: int = 0
    is_blocking: bool = False
    is_stunned: bool = False
    stun_timer: int = 0
    current_action: Optional[ActionType] = None
    action_timer: int = 0

    def __post_init__(self):
        self.hp = self.config.max_hp

    def reset(self, x: float, y: float):
        self.x = x
        self.y = y
        self.hp = self.config.max_hp
        self.is_blocking = False
        self.is_stunned = False
        self.stun_timer = 0
        self.current_action = None
        self.action_timer = 0


@dataclass
class Arena:
    radius: float = 50.0


def distance(b1: Bot, b2: Bot) -> float:
    return math.sqrt((b1.x - b2.x)**2 + (b1.y - b2.y)**2)


def normalize_vector(dx: float, dy: float) -> Tuple[float, float]:
    dist = math.sqrt(dx**2 + dy**2)
    if dist == 0:
        return (0.0, 0.0)
    return (dx / dist, dy / dist)


def get_tactic_weights(bot: Bot) -> Dict[ActionType, float]:
    """Возвращает текущие веса действий с учетом условий по ХП."""
    hp_percent = bot.hp / bot.config.max_hp
    weights = dict(bot.config.action_weights)
    
    # Проверяем условия тактики (сортируем по порогу ХП от большего к меньшему)
    for threshold in sorted(bot.config.tactic_conditions.keys(), reverse=True):
        if hp_percent <= threshold:
            weights = bot.config.tactic_conditions[threshold]
            break
    
    return weights


def choose_action(bot: Bot, opponent: Bot, arena: Arena) -> ActionType:
    """Выбирает действие на основе весов тактики."""
    if bot.is_stunned:
        return ActionType.MOVE  # Если оглушен, только движение
    
    weights = get_tactic_weights(bot)
    actions = list(weights.keys())
    action_weights = list(weights.values())
    
    # Корректировка весов в зависимости от ситуации
    dist = distance(bot, opponent)
    
    # Если далеко, увеличиваем шанс движения
    if dist > 15:
        if ActionType.MOVE in weights:
            action_weights[actions.index(ActionType.MOVE)] *= 2.0
        if ActionType.ATTACK in weights:
            action_weights[actions.index(ActionType.ATTACK)] *= 0.3
    
    # Если близко, увеличиваем шанс атаки
    if dist < 8:
        if ActionType.ATTACK in weights:
            action_weights[actions.index(ActionType.ATTACK)] *= 1.5
        if ActionType.MOVE in weights:
            action_weights[actions.index(ActionType.MOVE)] *= 0.7
    
    # Если мало ХП, увеличиваем шанс защиты
    if bot.hp < bot.config.max_hp * 0.3:
        if ActionType.BLOCK in weights:
            action_weights[actions.index(ActionType.BLOCK)] *= 2.0
    
    # Выбираем случайное действие с учетом весов
    return random.choices(actions, weights=action_weights, k=1)[0]


def execute_action(bot: Bot, opponent: Bot, arena: Arena, action: ActionType) -> str:
    """Выполняет действие и возвращает описание."""
    log = ""
    bot.is_blocking = False
    
    if bot.is_stunned:
        bot.stun_timer -= 1
        if bot.stun_timer <= 0:
            bot.is_stunned = False
        log += f"{bot.config.name} оглушен и пропускает ход!\n"
        return log
    
    bot.current_action = action
    
    if action == ActionType.MOVE:
        # Движение к противнику
        dx = opponent.x - bot.x
        dy = opponent.y - bot.y
        nx, ny = normalize_vector(dx, dy)
        bot.x += nx * bot.config.speed * 3
        bot.y += ny * bot.config.speed * 3
        log += f"{bot.config.name} двигается к противнику.\n"
        
    elif action == ActionType.DASH:
        # Рывок (быстрое движение)
        dx = opponent.x - bot.x
        dy = opponent.y - bot.y
        nx, ny = normalize_vector(dx, dy)
        bot.x += nx * bot.config.speed * 7
        bot.y += ny * bot.config.speed * 7
        
        # Проверяем, не вытолкнули ли мы противника при рывке
        dist = distance(bot, opponent)
        if dist < bot.config.radius + opponent.config.radius:
            # Толкаем противника
            push_dx = nx * 8
            push_dy = ny * 8
            opponent.x += push_dx
            opponent.y += push_dy
            log += f"{bot.config.name} делает рывок и толкает противника!\n"
        else:
            log += f"{bot.config.name} делает рывок вперед.\n"
            
    elif action == ActionType.ATTACK:
        dist = distance(bot, opponent)
        if dist < bot.config.radius + opponent.config.radius + 5:
            # Атака попадает
            damage = bot.config.attack_power
            if opponent.is_blocking:
                damage = max(1, damage - opponent.config.defense_power * 0.7)
            opponent.hp -= int(damage)
            log += f"{bot.config.name} атакует! Нанесено {int(damage)} урона.\n"
            
            # Шанс оглушить
            if random.random() < 0.15:
                opponent.is_stunned = True
                opponent.stun_timer = 2
                log += f"{opponent.config.name} оглушен!\n"
        else:
            log += f"{bot.config.name} атакует, но промахивается (слишком далеко).\n"
            
    elif action == ActionType.HEAVY_ATTACK:
        dist = distance(bot, opponent)
        if dist < bot.config.radius + opponent.config.radius + 7:
            # Тяжелая атака
            damage = bot.config.attack_power * 2.0
            if opponent.is_blocking:
                damage = max(2, damage - opponent.config.defense_power)
            opponent.hp -= int(damage)
            log += f"{bot.config.name} использует тяжелую атаку! Нанесено {int(damage)} урона.\n"
            
            # Сильный отброс
            dx = opponent.x - bot.x
            dy = opponent.y - bot.y
            nx, ny = normalize_vector(dx, dy)
            opponent.x += nx * 6
            opponent.y += ny * 6
            
            # Шанс оглушить выше
            if random.random() < 0.3:
                opponent.is_stunned = True
                opponent.stun_timer = 3
                log += f"{opponent.config.name} оглушен тяжелой атакой!\n"
        else:
            log += f"{bot.config.name} замахивается для тяжелой атаки, но не достает.\n"
            
    elif action == ActionType.BLOCK:
        bot.is_blocking = True
        log += f"{bot.config.name} встает в защитную стойку.\n"
        
    elif action == ActionType.COUNTER:
        bot.is_blocking = True
        dist = distance(bot, opponent)
        if dist < bot.config.radius + opponent.config.radius + 5:
            # Контратака
            damage = bot.config.attack_power * 1.2
            opponent.hp -= int(damage)
            log += f"{bot.config.name} контратакует! Нанесено {int(damage)} урона.\n"
        else:
            log += f"{bot.config.name} готовится к контратаке.\n"
    
    # Ограничиваем бота пределами арены (но не выталкиваем сразу)
    dist_from_center = math.sqrt(bot.x**2 + bot.y**2)
    if dist_from_center > arena.radius - bot.config.radius:
        # Возвращаем немного внутрь
        angle = math.atan2(bot.y, bot.x)
        bot.x = (arena.radius - bot.config.radius - 1) * math.cos(angle)
        bot.y = (arena.radius - bot.config.radius - 1) * math.sin(angle)
    
    return log


def check_ring_out(bot: Bot, arena: Arena) -> bool:
    """Проверяет, вышел ли бот за пределы круга."""
    dist_from_center = math.sqrt(bot.x**2 + bot.y**2)
    return dist_from_center > arena.radius


def simulate_battle(bot1_config: BotConfig, bot2_config: BotConfig, 
                   arena: Arena, max_turns: int = 100, verbose: bool = True) -> str:
    """Симулирует бой между двумя ботами."""
    bot1 = Bot(config=bot1_config)
    bot2 = Bot(config=bot2_config)
    
    # Размещаем ботов на противоположных сторонах арены
    bot1.reset(-15, 0)
    bot2.reset(15, 0)
    
    log = f"=== БОЙ НАЧАЛСЯ ===\n"
    log += f"{bot1.config.name} vs {bot2.config.name}\n"
    log += f"Арена: радиус {arena.radius}\n\n"
    
    turn = 0
    while turn < max_turns:
        turn += 1
        log += f"--- Ход {turn} ---\n"
        log += f"{bot1.config.name}: HP={bot1.hp}, Позиция=({bot1.x:.1f}, {bot1.y:.1f})\n"
        log += f"{bot2.config.name}: HP={bot2.hp}, Позиция=({bot2.x:.1f}, {bot2.y:.1f})\n"
        
        # Бот 1 выбирает и выполняет действие
        action1 = choose_action(bot1, bot2, arena)
        log += execute_action(bot1, bot2, arena, action1)
        
        # Бот 2 выбирает и выполняет действие
        action2 = choose_action(bot2, bot1, arena)
        log += execute_action(bot2, bot1, arena, action2)
        
        # Проверяем условия победы
        if bot1.hp <= 0 and bot2.hp <= 0:
            log += f"\n=== НИЧЬЯ! Оба бота уничтожены! ===\n"
            break
        elif bot1.hp <= 0:
            log += f"\n=== ПОБЕДА {bot2.config.name}! (HP противника исчерпаны) ===\n"
            break
        elif bot2.hp <= 0:
            log += f"\n=== ПОБЕДА {bot1.config.name}! (HP противника исчерпаны) ===\n"
            break
        
        ring_out_1 = check_ring_out(bot1, arena)
        ring_out_2 = check_ring_out(bot2, arena)
        
        if ring_out_1 and ring_out_2:
            log += f"\n=== НИЧЬЯ! Оба бота вытолкнуты за круг! ===\n"
            break
        elif ring_out_1:
            log += f"\n=== ПОБЕДА {bot2.config.name}! (Противник вытолкнут за круг) ===\n"
            break
        elif ring_out_2:
            log += f"\n=== ПОБЕДА {bot1.config.name}! (Противник вытолкнут за круг) ===\n"
            break
        
        if verbose:
            log += "\n"
    
    if turn >= max_turns:
        # Определяем победителя по оставшимся ХП
        if bot1.hp > bot2.hp:
            log += f"\n=== ПОБЕДА {bot1.config.name}! (Больше ХП после {max_turns} ходов) ===\n"
        elif bot2.hp > bot1.hp:
            log += f"\n=== ПОБЕДА {bot2.config.name}! (Больше ХП после {max_turns} ходов) ===\n"
        else:
            log += f"\n=== НИЧЬЯ! Одинаковое количество ХП после {max_turns} ходов ===\n"
    
    return log


def main():
    # Создаем арену
    arena = Arena(radius=50.0)
    
    # Настраиваем первого бота (агрессивный)
    bot1_config = BotConfig(
        name="Агрессор",
        max_hp=100,
        speed=1.2,
        attack_power=12.0,
        defense_power=4.0,
        action_weights={
            ActionType.MOVE: 2.0,
            ActionType.ATTACK: 6.0,
            ActionType.BLOCK: 1.0,
            ActionType.DASH: 2.0,
            ActionType.HEAVY_ATTACK: 3.0,
            ActionType.COUNTER: 0.5,
        },
        # Когда мало ХП, становится более осторожным
        tactic_conditions={
            0.3: {  # При 30% ХП
                ActionType.MOVE: 2.0,
                ActionType.ATTACK: 3.0,
                ActionType.BLOCK: 4.0,
                ActionType.DASH: 1.0,
                ActionType.HEAVY_ATTACK: 1.0,
                ActionType.COUNTER: 2.0,
            }
        }
    )
    
    # Настраиваем второго бота (защитный/тактический)
    bot2_config = BotConfig(
        name="Защитник",
        max_hp=120,
        speed=0.9,
        attack_power=9.0,
        defense_power=7.0,
        action_weights={
            ActionType.MOVE: 3.0,
            ActionType.ATTACK: 3.0,
            ActionType.BLOCK: 4.0,
            ActionType.DASH: 0.5,
            ActionType.HEAVY_ATTACK: 1.0,
            ActionType.COUNTER: 3.0,
        },
        # Когда мало ХП, еще больше защищается
        tactic_conditions={
            0.4: {  # При 40% ХП
                ActionType.MOVE: 1.0,
                ActionType.ATTACK: 2.0,
                ActionType.BLOCK: 6.0,
                ActionType.DASH: 0.5,
                ActionType.HEAVY_ATTACK: 0.5,
                ActionType.COUNTER: 4.0,
            }
        }
    )
    
    # Запускаем симуляцию
    result = simulate_battle(bot1_config, bot2_config, arena, max_turns=100, verbose=True)
    print(result)


if __name__ == "__main__":
    main()
