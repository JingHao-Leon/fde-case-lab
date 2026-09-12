"""NO.6 跨境物流装车：3D 装箱求解器。

对应真实场景：约 108 方货车装载电动车包装箱，98 方为保本线，
人工经验装车装载率仅 60%~65% 且需约 5 小时。

三种方法：
- NaiveRowPacker      经验装车基线（单层成排摆放）
- GreedyHeightMap     高度图贪心（单策略）
- MultiStrategyPacker 高度图 + 多策略排序（取最优），放置顺序即装载顺序，
  按"先里后外、先低后高"生成现场可执行的截面式装载序列。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

EPS = 1e-9
RES = 0.1  # 高度图网格分辨率（米）


@dataclass
class Placement:
    spec: str
    x: float  # 沿车厢长度方向，0 = 车厢最里端
    y: float  # 沿车厢宽度方向
    z: float  # 离地高度
    l: float  # x 方向占用
    w: float  # y 方向占用
    h: float  # z 方向占用
    item_id: int | None = None  # 货物唯一编号，用于车队装载时追踪归属


@dataclass
class PackResult:
    placements: list[Placement] = field(default_factory=list)
    loaded_m3: float = 0.0
    elapsed_s: float = 0.0
    method: str = ""


class BasePacker:
    def pack(self, items: list[dict], truck: tuple[float, float, float]) -> PackResult:
        raise NotImplementedError

    @staticmethod
    def fill_ratio(result: PackResult, truck: tuple[float, float, float]) -> float:
        L, W, H = truck
        return result.loaded_m3 / (L * W * H)


class NaiveRowPacker(BasePacker):
    """模拟"老师傅"经验装车：底面占地大的先放，单层成排摆放，不向上堆叠。

    这是对案例中"整体空间利用率通常只有 60%~65%"的人工方式的模拟基线。
    """

    def pack(self, items: list[dict], truck: tuple[float, float, float]) -> PackResult:
        t0 = time.perf_counter()
        L, W, _ = truck
        placed: list[Placement] = []
        loaded = 0.0
        row_x, row_y, row_depth = 0.0, 0.0, 0.0
        for it in sorted(items, key=lambda d: -(d["l"] * d["w"])):
            l, w = it["l"], it["w"]
            if row_y + w > W + EPS:  # 当前行放不下，另起一排
                row_x += row_depth
                row_y, row_depth = 0.0, 0.0
            if row_x + l > L + EPS:
                break  # 车厢装满，剩余货不装
            placed.append(Placement(it["spec"], row_x, row_y, 0.0, l, w, it["h"], it.get("id")))
            loaded += l * w * it["h"]
            row_y += w
            row_depth = max(row_depth, l)
        res = PackResult(placed, loaded, time.perf_counter() - t0, "naive_row")
        return res


class HeightMapPacker(BasePacker):
    """高度图装箱：把车厢离散成 俯视网格 + 每格高度，逐一放置货物。

    - 放置位置选择：最低堆叠高度优先，同高时先放车厢最里端（x 最小），
      因此放置序列天然构成"由内向外、由低到高"的截面式装载顺序。
    - 大件（任一边 > 1.2m）只允许绕竖直轴旋转 90°（纸箱不翻面）；
      小件允许六向旋转，用于装填大件留下的缝隙。
    """

    def __init__(self, strategy: str = "volume", preserve_order: bool = False):
        self.strategy = strategy
        self.preserve_order = preserve_order

    def _sort_items(self, items: list[dict]) -> list[dict]:
        if self.preserve_order:
            return list(items)
        key = {
            "volume": lambda d: -(d["l"] * d["w"] * d["h"]),
            "footprint": lambda d: -(d["l"] * d["w"]),
            "tall_first": lambda d: (-d["h"], -(d["l"] * d["w"])),
            "long_side": lambda d: (-max(d["l"], d["w"]), -(d["l"] * d["w"] * d["h"])),
        }[self.strategy]
        return sorted(items, key=key)

    def pack(self, items: list[dict], truck: tuple[float, float, float]) -> PackResult:
        t0 = time.perf_counter()
        L, W, H = truck
        nx, ny = int(L / RES), int(W / RES)  # floor：网格不超出车厢内净尺寸
        hmap = np.zeros((ny, nx), dtype=np.float32)
        placed: list[Placement] = []
        loaded = 0.0
        for it in self._sort_items(items):
            l, w, h = it["l"], it["w"], it["h"]
            small = max(l, w, h) <= 1.2
            # (x向, y向, z向) 候选：大件只直立+绕竖轴转90°；小件六向
            if small:
                orients = {(l, w, h), (w, l, h), (l, h, w), (h, l, w), (w, h, l), (h, w, l)}
            else:
                orients = {(l, w, h), (w, l, h)}
            best = None  # (新高度, x_idx, y_idx, l_eff, w_eff, 高度)
            for lx, wy, hz in orients:
                # 格数向上取整：网格预留量 >= 箱体实际尺寸，保证连续坐标下不重叠
                dl = -(-int(round(lx * 100)) // int(RES * 100))
                dw = -(-int(round(wy * 100)) // int(RES * 100))
                if dl > nx or dw > ny:
                    continue
                l_eff, w_eff = dl * RES, dw * RES
                win = np.lib.stride_tricks.sliding_window_view(hmap, (dw, dl))
                foot_max = win.max(axis=(2, 3))
                new_h = foot_max + hz
                valid = new_h <= H + EPS
                if not valid.any():
                    continue
                ys, xs = np.nonzero(valid)
                # 最低新高度优先；同高先放最里端（x 小），再靠边（y 小）
                order = np.lexsort((ys, xs, new_h[ys, xs]))
                y0, x0 = ys[order[0]], xs[order[0]]
                cand = (float(new_h[y0, x0]), int(x0), int(y0), l_eff, w_eff, hz)
                if best is None or (cand[0], cand[1], cand[2]) < (best[0], best[1], best[2]):
                    best = cand
            if best is None:
                continue  # 所有朝向都放不下
            _, x0, y0, l_eff, w_eff, hz = best
            cells_x, cells_y = int(round(l_eff / RES)), int(round(w_eff / RES))
            z = float(hmap[y0 : y0 + cells_y, x0 : x0 + cells_x].max())
            hmap[y0 : y0 + cells_y, x0 : x0 + cells_x] = z + hz
            placed.append(Placement(it["spec"], x0 * RES, y0 * RES, z, l_eff, w_eff, hz,
                                    it.get("id")))
            loaded += l_eff * w_eff * hz
        res = PackResult(placed, loaded, time.perf_counter() - t0, f"heightmap:{self.strategy}")
        return res


STRATEGIES = ("volume", "footprint", "tall_first", "long_side")


class MultiStrategyPacker(BasePacker):
    """多策略排序 + 取最优：分别按 4 种排序策略各跑一遍高度图装箱，
    取装载量最高的结果（确定性，无随机重启）。"""

    def pack(self, items: list[dict], truck: tuple[float, float, float]) -> PackResult:
        t0 = time.perf_counter()
        best = None
        for s in STRATEGIES:
            r = HeightMapPacker(s).pack(items, truck)
            if best is None or r.loaded_m3 > best.loaded_m3:
                best = r
        best.elapsed_s = time.perf_counter() - t0
        best.method = "multi_strategy"
        return best


class OptimizedPacker(BasePacker):
    """优化版：多策略 × 种子化随机重启 × 小件六向旋转填缝。

    在多策略基础上，对排序结果做受控扰动（固定种子的块内交换，保证可复现），
    重复求解取装载量最高的方案。对应业务诉求：每车都要稳定冲过 98 方保本线。
    """

    def __init__(self, n_restarts: int = 24, seed: int = 7):
        self.n_restarts = n_restarts
        self.seed = seed

    @staticmethod
    def _perturb(items: list[dict], rng: random.Random) -> list[dict]:
        out = list(items)
        for i in range(0, len(out) - 2, 3):
            j = rng.randrange(i, min(i + 3, len(out)))
            out[i], out[j] = out[j], out[i]
        return out

    def pack(self, items: list[dict], truck: tuple[float, float, float]) -> PackResult:
        import random as _random

        t0 = time.perf_counter()
        best = None
        per_strategy = max(1, self.n_restarts // len(STRATEGIES))
        for s in STRATEGIES:
            base = HeightMapPacker(s)._sort_items(items)
            for k in range(per_strategy):
                if k == 0:
                    seq = base  # 不扰动的确定性别名
                else:
                    seq = self._perturb(base, _random.Random(self.seed * 977 + k * 31))
                r = HeightMapPacker(s, preserve_order=True).pack(seq, truck)
                if best is None or r.loaded_m3 > best.loaded_m3:
                    best = r
        best.elapsed_s = time.perf_counter() - t0
        best.method = f"optimized(r={self.n_restarts})"
        return best


def validate_no_overlap(placed: list[Placement], truck: tuple[float, float, float]) -> bool:
    """两两 AABB 校验：任意两箱不允许体积重叠，且必须在车厢内。"""
    L, W, H = truck
    for i, a in enumerate(placed):
        if not (0 <= a.x and a.x + a.l <= L + 1e-6 and 0 <= a.y and a.y + a.w <= W + 1e-6
                and a.z + a.h <= H + 1e-6):
            return False
        for b in placed[i + 1 :]:
            ox = min(a.x + a.l, b.x + b.l) - max(a.x, b.x)
            oy = min(a.y + a.w, b.y + b.w) - max(a.y, b.y)
            oz = min(a.z + a.h, b.z + b.h) - max(a.z, b.z)
            if ox > 1e-6 and oy > 1e-6 and oz > 1e-6:
                return False
    return True


def pack_fleet(packer: BasePacker, items: list[dict],
               truck: tuple[float, float, float]) -> list[PackResult]:
    """车队逐车装载：当前车装不下任何剩余货物时换下一车，直到全部装完。"""
    remaining = list(items)
    trucks: list[PackResult] = []
    while remaining:
        r = packer.pack(remaining, truck)
        placed_ids = {p.item_id for p in r.placements}
        remaining = [it for it in remaining if it.get("id") not in placed_ids]
        trucks.append(r)
    return trucks


def profit_usd(loaded_m3: float, break_even: float = 98.0, usd_per_m3: float = 100.0) -> float:
    """按"98 方保本、每超 1 方增收 100 美元"计费结构计算单车盈亏。"""
    return (loaded_m3 - break_even) * usd_per_m3

