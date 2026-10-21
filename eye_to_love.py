#!/usr/bin/env python3
"""
Eye -> Love (Procedural ASCII Shader Animation)
100% Pure Standard-Library Python — ZERO external packages required!
(No numpy, no pillow, no pip install needed — runs directly in VS Code!)

Run in VS Code or terminal:
    python eye_to_love.py

Window Controls:
    Space : Pause / Resume
    R     : Restart animation from 0.0s
    Esc   : Close window
"""

import base64
import math
import time
import zlib

# 70-character Paul Bourke luminance ramp (dark -> bright)
RAMP = " .'`^\",:;Il!i><~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
N_RAMP = len(RAMP)

# Grid dimensions matching the video's "Eye -> Space" window (104 cols x 32 rows)
COLS = 104
ROWS = 32
CELL_W = 8
CELL_H = 16
WIN_W = COLS * CELL_W
WIN_H = ROWS * CELL_H

# Compressed 8x16 DejaVuSansMono-Bold bitmap font for ASCII 32..126 (zero external font/PIL dependency)
_FONT_B64 = (
    "eNp1VLFq3EAQPUxYDF6EK7OFEP4AF+JIoWIQrq4yV4cUx3IcmxRiES4OQcT6n/IF5g6SMsbluUiq"
    "K0PwB8iZXe3srhzncXfSu5md3Zn3pNnsDQgHvHi+QUwSLi7u3l8Nnz9QOvQdFCsDfkX78LAVy7Oz"
    "zKdXm7b88vOHvkvqx2IcWYnAC7e8PBce56XPXwGsxPSALy+TIv7fMhCAN9ryN4xxforVL+X1mKuV"
    "MUppWtL5/Q3VWrKMi1IGvmCQMbboqYMcmsZwzj3vpeyXjC2pHtzKXiGIm4zz3DZNcQylcTyP0jW7"
    "qaZHT/r1PPR7UnS/uuIk9joM9hNw3xWs6O7Dfoyn+sJ69fj89flxta5HvQBgY9RiT/3g2eyX+s/n"
    "0mKeU1zb0ytN8zAYdN9XXMZ5SFyyrT23i439ofxX868zhxuqjzt1XdOoT55LD8o//h6Gw2G324X6"
    "263RWqs4b3VM5u3E6ZPzUTx7F/rTfdwPlGzRAAtaP5Bhk35SPb/hfYMzJT33+6enwTqOzqsABIA6"
    "ev4drVgl9QzLclG1vr/8PMALcC0v8aE55Zwxq54I8BsK0IvZ/1GKf/5ChxvS207WTUj1Ie4cMAf/"
    "NDFWaxyYruN6pQa5HuOFVXIyH1TUOgYtvpzUV8Hb4xM4vi9y7BJyB1fB5qsGDeDz/5Qeooj2PzgE"
    "ntYnhaM+FO+DA3w/bp6OV26HuH6DBgj6l6Wx0SruPz4Pdcqvov7WAYePaIAYtwZIOLoP/RIExDdG"
    "Lsp21CNzs2ntTxHf1tGBLiJcVhsVvR1fxn8BSh3tvQ=="
)


def _unpack_font():
    raw = zlib.decompress(base64.b64decode(_FONT_B64))
    glyphs = {}
    for idx, code in enumerate(range(32, 127)):
        ch = chr(code)
        base = idx * 16
        glyphs[ch] = [raw[base + y] << 15 for y in range(16)]
    return glyphs


GLYPH_MASKS = _unpack_font()
RAMP_GLYPHS = [GLYPH_MASKS[ch] for ch in RAMP]


def ss(a, b, x):
    """GLSL-style smoothstep(a, b, x) supporting both a < b and a > b."""
    t = (x - a) / (b - a + 1e-12)
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return t * t * (3.0 - 2.0 * t)


def clamp(x, a, b):
    return a if x < a else (b if x > b else x)


def make_noise_tables():
    """Build 512x512 pre-interpolated periodic noise lookup tables TS and TW."""
    state = 42

    def next_rand():
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    N = 256

    def build_smooth(layers):
        acc = [0.0] * (N * N)
        total_w = 0.0
        for step, weight in layers:
            gh = N // step
            gw = N // step
            g = [next_rand() for _ in range(gh * gw)]
            for y in range(N):
                yf = y / step
                yi = int(yf)
                y0 = yi % gh
                y1 = (y0 + 1) % gh
                fy = yf - yi
                fy = fy * fy * (3.0 - 2.0 * fy)
                row_off = y * N
                y0_off = y0 * gw
                y1_off = y1 * gw
                for x in range(N):
                    xf = x / step
                    xi = int(xf)
                    x0 = xi % gw
                    x1 = (x0 + 1) % gw
                    fx = xf - xi
                    fx = fx * fx * (3.0 - 2.0 * fx)
                    v00 = g[y0_off + x0]
                    v10 = g[y0_off + x1]
                    v01 = g[y1_off + x0]
                    v11 = g[y1_off + x1]
                    val = (
                        v00 * (1.0 - fx) * (1.0 - fy)
                        + v10 * fx * (1.0 - fy)
                        + v01 * (1.0 - fx) * fy
                        + v11 * fx * fy
                    )
                    acc[row_off + x] += val * weight
            total_w += weight

        mn = min(acc)
        mx = max(acc)
        span = (mx - mn) or 1.0
        return [(v - mn) / span for v in acc]

    TS = build_smooth([(16, 0.50), (8, 0.30), (4, 0.15), (2, 0.05)])
    TW = build_smooth([(32, 0.45), (16, 0.30), (8, 0.15), (4, 0.10)])
    return TS, TW, state


TS, TW, _RNG_STATE = make_noise_tables()


def make_stars(seed_state, count=320):
    state = seed_state

    def rand():
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t = (t ^ (t + ((t ^ (t >> 7)) * (t | 61)))) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    stars = []
    half = count // 2
    for i in range(count):
        if i < half:
            u1 = max(1e-6, rand())
            u2 = rand()
            mag = math.sqrt(-2.0 * math.log(u1))
            sx = mag * math.cos(2.0 * math.pi * u2) * 0.22
            sy = mag * math.sin(2.0 * math.pi * u2) * 0.16
        else:
            sx = (rand() * 2.0 - 1.0) * 0.95
            sy = (rand() * 2.0 - 1.0) * 0.62
        sz0 = 0.05 + rand() * 0.95
        sbright = 0.55 + rand() * 0.45
        sphase = rand() * 2.0 * math.pi
        r = rand()
        ssize = 0 if r < 0.52 else (1 if r < 0.82 else 2)
        stars.append((sx, sy, sz0, sbright, sphase, ssize))
    return stars


STARS = make_stars(_RNG_STATE, 320)
WO = 0.43

# Precompute screen coordinate arrays
U_SCR = [-0.54 + (c / (COLS - 1)) * 1.08 for c in range(COLS)]
V_SCR = [-0.39 + (r / (ROWS - 1)) * 0.68 for r in range(ROWS)]


def scene_params(t):
    open_in = ss(0.85, 1.95, t)
    blink = 0.78 * math.exp(-(((t - 3.15) / 0.13) ** 2))
    widen = 0.12 * ss(4.5, 7.0, t)
    ou = clamp(open_in - blink + widen, 0.0, 1.08)

    gaze_fade = ss(5.2, 4.0, t)
    gx = (
        -0.055 * math.exp(-(((t - 2.45) / 0.55) ** 2))
        + 0.048 * math.exp(-(((t - 3.65) / 0.50) ** 2))
    ) * gaze_fade
    gy = (
        0.010 * math.sin(t * 2.1)
        - 0.014 * math.exp(-(((t - 3.15) / 0.25) ** 2))
    ) * gaze_fade

    if t < 4.3:
        z = 1.0 + 0.05 * ss(1.5, 4.3, t)
    else:
        zt = (t - 4.3) / 9.0
        z = 1.05 * math.exp(3.40 * (zt ** 1.32))

    Rp = 0.058 + 0.052 * ss(4.5, 8.8, t)
    return z, ou, gx, gy, Rp


# Reusable frame buffers
_N_CELLS = ROWS * COLS
_EYE_R = [0.0] * _N_CELLS
_EYE_G = [0.0] * _N_CELLS
_EYE_B = [0.0] * _N_CELLS
_PM = [0.0] * _N_CELLS
_SP_R = [0.0] * _N_CELLS
_SP_G = [0.0] * _N_CELLS
_SP_B = [0.0] * _N_CELLS
_STAR_CH = [""] * _N_CELLS

# Scanline cache for ultra-fast pure-Python PPM generation
_SCANLINE_CACHE = {0: b"\x00" * 24}


def _build_scanline(key):
    mask_byte = key >> 15
    if mask_byte == 0:
        res = b"\x00" * 24
        _SCANLINE_CACHE[key] = res
        return res
    r = ((key >> 10) & 31) << 3
    g = ((key >> 5) & 31) << 3
    b = (key & 31) << 3
    rgb_on = bytes((r, g, b))
    rgb_off = b"\x00\x00\x00"
    res = b"".join(rgb_on if (mask_byte & (1 << (7 - bit))) else rgb_off for bit in range(8))
    _SCANLINE_CACHE[key] = res
    return res


def render_frame_ppm(t):
    """
    Compute the entire frame in pure Python and return binary P6 PPM bytes for Tkinter.
    """
    exp = math.exp
    sin = math.sin
    cos = math.cos
    sqrt = math.sqrt
    atan2 = math.atan2
    asin = math.asin

    z, ou, gx, gy, Rp = scene_params(t)
    inv_z = 1.0 / z
    zoom_cy = -0.05 * ss(3.5, 1.0, z)
    space_vis = ss(4.6, 6.2, t)
    deep_space = ss(9.2, 11.6, t)
    fade_in = ss(0.45, 1.25, t)

    # 3D Red Love Heart parameters
    flight = clamp((t - 7.2) / 6.8, 0.0, 1.0)
    flight_smooth = flight * flight * (3.0 - 2.0 * flight)
    beat_phase = (t * 1.35) % 1.0
    lub = exp(-(((beat_phase - 0.18) / 0.065) ** 2))
    dub = 0.65 * exp(-(((beat_phase - 0.36) / 0.08) ** 2))
    heartbeat = 1.0 + 0.065 * (lub + dub) * flight_smooth
    halo_pulse = ss(0.04, 0.24, flight) * (1.0 + 0.25 * (lub + dub))
    heart_vis = ss(0.04, 0.18, flight)

    R_heart = (0.010 + 0.235 * (flight_smooth ** 1.10)) * heartbeat
    inv_Rh = 1.0 / (R_heart + 1e-6)
    tilt = 0.06 * sin(t * 1.4)
    sway_inv = 1.0 / (1.0 - 0.08 * (sin(t * 1.1) ** 2))
    ct, st = cos(tilt), sin(tilt)

    R_iris = 0.172
    inv_R_iris = 1.0 / R_iris
    r_p_norm_p15 = (Rp / R_iris) + 0.15
    cr_pos = 0.075 + 0.03 * (1.0 - ou)
    spec_fade = ss(9.0, 2.2, z)
    ou_vis = ss(0.01, 0.08, ou)
    gl_ou = 0.55 * ss(0.12, 0.5, ou)
    cg_ou = 0.85 * ss(0.1, 0.5, ou)
    lash_ou = (1.0 - 0.3 * ou) * 0.9

    # Precompute 1D horizontal eye terms across COLS
    u_arr = [0.0] * COLS
    s_arr = [0.0] * COLS
    abs_s_arr = [0.0] * COLS
    sb_arr = [0.0] * COLS
    y_up_arr = [0.0] * COLS
    y_lo_arr = [0.0] * COLS
    y_mid_arr = [0.0] * COLS
    s_mask_in = [0.0] * COLS
    corner_red_arr = [0.0] * COLS
    eb_s_mask = [0.0] * COLS
    lash_s_mask = [0.0] * COLS
    wl_s_mask = [0.0] * COLS
    gl_s_mask = [0.0] * COLS

    for c in range(COLS):
        u = U_SCR[c] * inv_z + gx
        u_arr[c] = u
        s = u / WO
        s_arr[c] = s
        a_s = abs(s)
        abs_s_arr[c] = a_s
        sb = clamp(1.0 - a_s, 0.0, 1.0)
        sb_arr[c] = sb

        arch = clamp(1.0 - s * s, 0.0, 1.0)
        closed_y = 0.020 * (1.0 - arch * 0.4)
        open_up = -0.185 * (arch ** 0.76) - 0.014 * exp(-(((s - 0.12) / 0.45) ** 2))
        open_lo = 0.125 * (arch ** 0.84) + 0.010 * exp(-(((s + 0.10) / 0.50) ** 2))

        yup = closed_y * (1.0 - ou) + open_up * ou
        ylo = (closed_y + 0.002) * (1.0 - ou) + open_lo * ou
        y_up_arr[c] = yup
        y_lo_arr[c] = ylo
        y_mid_arr[c] = 0.5 * (yup + ylo)

        s_mask_in[c] = ss(1.04, 0.91, a_s) * ou_vis
        cr = clamp((a_s - 0.50) / 0.50, 0.0, 1.0)
        corner_red_arr[c] = cr * sqrt(cr)
        eb_s_mask[c] = ss(1.32, 0.82, a_s)
        lash_s_mask[c] = ss(1.02, 0.82, a_s)
        wl_s_mask[c] = ss(1.02, 0.85, a_s) * 0.7
        gl_s_mask[c] = ss(1.0, 0.8, a_s)

    ts_tab = TS
    tw_tab = TW

    for r in range(ROWS):
        v_scr = V_SCR[r]
        v_rel = v_scr - zoom_cy
        v = v_rel * inv_z + gy
        v_sh_term = 0.10 * exp(-(((v + 0.20) / 0.09) ** 2))
        ty_skin = (int(v * 120.0 + 100.0) & 255) << 8
        ty_hair = (int(v * 30.0) & 255) << 8
        ty_lash = (int(v * 80.0) & 255) << 8
        ty_gl = (int(v * 60.0) & 255) << 8
        ty_sp = (int(v * 150.0 + 3.0) & 255) << 8
        row_base = r * COLS

        for c in range(COLS):
            idx = row_base + c
            u_scr = U_SCR[c]
            u = u_arr[c]
            s = s_arr[c]
            sb = sb_arr[c]
            vt = v - 0.012 * s

            yup = y_up_arr[c]
            ylo = y_lo_arr[c]
            upper = vt < y_mid_arr[c]
            du = yup - vt if yup > vt else 0.0
            dl = vt - ylo if vt > ylo else 0.0

            m_in = (
                ss(yup - 0.008, yup + 0.006, vt)
                * ss(ylo + 0.008, ylo - 0.006, vt)
                * s_mask_in[c]
            )

            in_r = in_g = in_b = 0.0
            pm_raw = 0.0
            if m_in > 0.001:
                rb2 = (u / 0.45) ** 2 + (vt / 0.27) ** 2
                sclera_sh = clamp(1.08 - 0.50 * (rb2 ** 0.775), 0.20, 1.0)
                lid_cast = ss(yup - 0.004, yup + 0.045, vt)
                sclera_sh *= 0.48 + 0.52 * lid_cast

                vein_n = tw_tab[((int(vt * 110.0 + 29.0) & 255) << 8) | (int(u * 110.0 + 13.0) & 255)]
                cr_mix = corner_red_arr[c] * (0.45 + 0.35 * vein_n)
                sc_r = (0.94 * (1.0 - cr_mix) + 0.84 * cr_mix) * sclera_sh
                sc_g = (0.90 * (1.0 - cr_mix) + 0.48 * cr_mix) * sclera_sh
                sc_b = (0.88 * (1.0 - cr_mix) + 0.44 * cr_mix) * sclera_sh

                iu = u - gx
                iv = vt - gy
                ir = sqrt(iu * iu + iv * iv + 1e-10)
                pm_raw = ss(Rp + 0.008, Rp - 0.006, ir)
                m_iris = ss(R_iris + 0.008, R_iris - 0.008, ir)

                if m_iris > 0.001:
                    itheta = atan2(iv, iu)
                    r_norm = ir * inv_R_iris
                    ang_u = int((itheta / (2.0 * math.pi) + 0.5) * 180.0) & 255
                    rad_v = int(r_norm * 45.0) & 255
                    f1 = tw_tab[(rad_v << 8) | ang_u]
                    f2 = ts_tab[(((int(r_norm * 67.5 + 19.0)) & 255) << 8) | ((ang_u * 2 + 37) & 255)]
                    fibers = clamp(0.55 * f1 + 0.45 * f2 + 0.22 * sin(itheta * 40.0 + f1 * 4.0), 0.0, 1.0)

                    collarette = exp(-(((r_norm - r_p_norm_p15) / 0.14) ** 2)) * 0.65
                    limbal_ring = ss(0.74, 0.98, r_norm) * 0.80
                    iris_light = (0.55 + 0.45 * lid_cast) * (0.88 + 0.32 * clamp(iv * inv_R_iris + 0.35, 0.0, 1.0))

                    ir_r = 0.52 * (1.0 - fibers) + 0.82 * fibers
                    ir_g = 0.26 * (1.0 - fibers) + 0.48 * fibers
                    ir_b = 0.13 * (1.0 - fibers) + 0.24 * fibers
                    ir_r = ir_r * (1.0 - collarette) + 0.95 * collarette
                    ir_g = ir_g * (1.0 - collarette) + 0.64 * collarette
                    ir_b = ir_b * (1.0 - collarette) + 0.36 * collarette
                    ir_r = (ir_r * (1.0 - limbal_ring) + 0.08 * limbal_ring) * iris_light
                    ir_g = (ir_g * (1.0 - limbal_ring) + 0.04 * limbal_ring) * iris_light
                    ir_b = (ir_b * (1.0 - limbal_ring) + 0.03 * limbal_ring) * iris_light

                    in_r = sc_r * (1.0 - m_iris) + ir_r * m_iris
                    in_g = sc_g * (1.0 - m_iris) + ir_g * m_iris
                    in_b = sc_b * (1.0 - m_iris) + ir_b * m_iris
                else:
                    in_r, in_g, in_b = sc_r, sc_g, sc_b

                in_r = in_r * (1.0 - pm_raw) + 0.01 * pm_raw
                in_g = in_g * (1.0 - pm_raw) + 0.01 * pm_raw
                in_b = in_b * (1.0 - pm_raw) + 0.015 * pm_raw

                sp1 = exp(-(((iu - 0.046) / 0.024) ** 2 + ((iv + 0.040) / 0.018) ** 2)) * 1.15
                sp2 = exp(-(((iu + 0.052) / 0.014) ** 2 + ((iv - 0.042) / 0.011) ** 2)) * 0.65
                sp_tot = (sp1 + sp2) * spec_fade * lid_cast
                in_r += sp_tot
                in_g += sp_tot * 0.98
                in_b += sp_tot * 0.95

            dd = du if upper else dl
            tx = ts_tab[ty_skin | (int(u * 120.0 + 100.0) & 255)]
            skin_mul = 0.90 + 0.20 * tx
            sk_r = 0.62 * skin_mul
            sk_g = 0.40 * skin_mul
            sk_b = 0.29 * skin_mul

            sh = 0.50 + 0.50 * ss(0.0, 0.30, dd) + v_sh_term
            if upper:
                sh -= 0.42 * exp(-(((du - cr_pos) / 0.020) ** 2))
            else:
                sh += 0.08 * exp(-(((dl - 0.09) / 0.04) ** 2))
            sk_r *= sh
            sk_g *= sh
            sk_b *= sh

            if upper:
                lidzone = ss(cr_pos, cr_pos * 0.4, du) * 0.5
                sk_r = sk_r * (1.0 - lidzone) + (0.68 * sh) * lidzone
                sk_g = sk_g * (1.0 - lidzone) + (0.40 * sh) * lidzone
                sk_b = sk_b * (1.0 - lidzone) + (0.31 * sh) * lidzone

            eb = exp(-(((vt + 0.34 + 0.09 * s * s) / (0.042 + 0.014 * sb)) ** 2)) * eb_s_mask[c]
            if eb > 0.002:
                hair = 0.55 + 0.9 * tw_tab[ty_hair | (int(u * 90.0) & 255)]
                eb_mix = clamp(eb * hair, 0.0, 0.92)
                sk_r = sk_r * (1.0 - eb_mix) + 0.10 * eb_mix
                sk_g = sk_g * (1.0 - eb_mix) + 0.06 * eb_mix
                sk_b = sk_b * (1.0 - eb_mix) + 0.04 * eb_mix

            if upper:
                if du < 0.065:
                    sgn = 1.0 if s >= 0.0 else -1.0
                    lash_n = tw_tab[ty_lash | (int(u * 80.0) & 255)]
                    lash_wave = 0.5 + 0.5 * sin((s + du * 0.55 * sgn) * 125.0 + lash_n * 2.2)
                    lashes_u = exp(-((du / (0.016 + 0.024 * lash_wave * sb)) ** 2)) * lash_s_mask[c]
                    line = max(exp(-((du / 0.010) ** 2)), lashes_u * 0.88)
                    l_mix = clamp(line * lash_ou, 0.0, 1.0)
                    sk_r = sk_r * (1.0 - l_mix) + 0.05 * l_mix
                    sk_g = sk_g * (1.0 - l_mix) + 0.03 * l_mix
                    sk_b = sk_b * (1.0 - l_mix) + 0.022 * l_mix
            else:
                if dl < 0.04:
                    wl = ss(0.014, 0.0, dl) * wl_s_mask[c]
                    sk_r = sk_r * (1.0 - wl) + 0.74 * wl
                    sk_g = sk_g * (1.0 - wl) + 0.34 * wl
                    sk_b = sk_b * (1.0 - wl) + 0.30 * wl

                    gl_n = tw_tab[ty_gl | (int(u * 60.0) & 255)]
                    gl = exp(-(((dl - 0.016) / 0.006) ** 2)) * (0.35 + 0.65 * gl_n) * gl_s_mask[c]
                    gl_add = gl * gl_ou
                    sk_r += gl_add
                    sk_g += gl_add * 0.85
                    sk_b += gl_add * 0.75

            if tw_tab[ty_sp | (int(u * 150.0 + 7.0) & 255)] > 0.985:
                sp_ = 0.35 * (0.4 + tx) * ss(0.0, 0.3, dd)
                sk_r += sp_
                sk_g += sp_ * 0.9
                sk_b += sp_ * 0.8

            col_r = sk_r * (1.0 - m_in) + in_r * m_in
            col_g = sk_g * (1.0 - m_in) + in_g * m_in
            col_b = sk_b * (1.0 - m_in) + in_b * m_in

            cg = exp(-(((u + WO * 0.90) / 0.045) ** 2 + ((vt - 0.025) / 0.032) ** 2)) * cg_ou
            if cg > 0.002:
                col_r = col_r * (1.0 - cg) + 0.82 * cg
                col_g = col_g * (1.0 - cg) + 0.42 * cg
                col_b = col_b * (1.0 - cg) + 0.38 * cg

            _EYE_R[idx] = clamp(col_r, 0.0, 1.0)
            _EYE_G[idx] = clamp(col_g, 0.0, 1.0)
            _EYE_B[idx] = clamp(col_b, 0.0, 1.0)
            _PM[idx] = pm_raw * m_in
            _STAR_CH[idx] = ""

            # --- SPACE 3D RED LOVE HEART SHADER ---
            if space_vis > 0.001:
                raw_x = u_scr * inv_Rh
                raw_y = -v_rel * inv_Rh - 0.08
                hx = (raw_x * ct - raw_y * st) * sway_inv
                hy = raw_x * st + raw_y * ct
                width_scale = 0.84 + 0.34 * clamp((hy + 0.55) / 1.25, 0.0, 1.0)
                x_norm = hx / width_scale
                y_lobe = (hy - 0.68 * (abs(x_norm) ** 0.72) + 0.24) / 0.86
                hr2 = x_norm * x_norm + y_lobe * y_lobe
                hr = sqrt(hr2)

                halo = exp(-(((hr - 0.94) / 0.26) ** 2)) * halo_pulse
                sp_r = halo * 0.62
                sp_g = halo * 0.08
                sp_b = halo * 0.18

                if hr < 1.05 and flight > 0.04:
                    cleft = 0.26 * exp(-((hx / 0.20) ** 2)) * clamp((hy - 0.02) / 0.65, 0.0, 1.0)
                    hz = sqrt(max(0.0, 1.0 - hr2)) * (1.0 - cleft)

                    sgn_hx = 1.0 if hx >= 0.0 else -1.0
                    nx = x_norm * 0.85 + 0.25 * sgn_hx * exp(-((hx / 0.22) ** 2)) * clamp(hy, 0.0, 1.0)
                    ny = y_lobe * 0.85
                    nz = max(0.15, hz)
                    n_len = sqrt(nx * nx + ny * ny + nz * nz + 1e-8)
                    nx /= n_len
                    ny /= n_len
                    nz /= n_len

                    lat_h = asin(clamp(ny, -1.0, 1.0))
                    lon_h = atan2(nx, nz) + t * 0.60
                    n_swirl = tw_tab[
                        ((int((lat_h / math.pi + 0.5) * 28.0) & 255) << 8)
                        | (int((lon_h / (2.0 * math.pi) + 0.5) * 28.0) & 255)
                    ]
                    band_wave = cos(hy * 14.0 - t * 1.8 + (n_swirl - 0.5) * 1.2)
                    bands = clamp(0.55 + 0.45 * band_wave, 0.0, 1.0)

                    h_r = 0.38 * (1.0 - bands) + 0.95 * bands
                    h_g = 0.03 * (1.0 - bands) + 0.14 * bands
                    h_b = 0.08 * (1.0 - bands) + 0.26 * bands

                    ndotl = clamp(nx * (-0.32) + ny * 0.38 + nz * 0.868, 0.0, 1.0)
                    spec = clamp((nx * (-0.32) + ny * 0.38 + nz * 1.868) / 1.933, 0.0, 1.0) ** 14.0
                    limb = (hz ** 0.34) * (0.32 + 0.85 * ndotl)
                    h_r *= limb
                    h_g *= limb
                    h_b *= limb

                    hi_mix = clamp(spec * 0.92 + (bands ** 2.2) * ndotl * 0.55, 0.0, 1.0)
                    h_r = h_r * (1.0 - hi_mix) + 1.00 * hi_mix
                    h_g = h_g * (1.0 - hi_mix) + 0.72 * hi_mix
                    h_b = h_b * (1.0 - hi_mix) + 0.80 * hi_mix

                    rim = ((1.0 - hz) ** 2.0) * 0.62
                    h_r += rim * 0.85
                    h_g += rim * 0.12
                    h_b += rim * 0.24

                    h_mask = ss(1.02, 0.92, hr) * heart_vis
                    sp_r = sp_r * (1.0 - h_mask) + h_r * h_mask
                    sp_g = sp_g * (1.0 - h_mask) + h_g * h_mask
                    sp_b = sp_b * (1.0 - h_mask) + h_b * h_mask

                _SP_R[idx] = sp_r
                _SP_G[idx] = sp_g
                _SP_B[idx] = sp_b
            else:
                _SP_R[idx] = 0.0
                _SP_G[idx] = 0.0
                _SP_B[idx] = 0.0

    # --- 3D STARFIELD WITH 4-POINT CROSS FLARES ---
    if space_vis > 0.001:
        u_min, u_max = -0.54, 0.54
        v_min, v_max = -0.34, 0.34

        def heart_hr(u_val, v_val):
            rx = u_val * inv_Rh
            ry = -v_val * inv_Rh - 0.08
            hx_ = (rx * ct - ry * st) * sway_inv
            hy_ = rx * st + ry * ct
            ws_ = 0.84 + 0.34 * clamp((hy_ + 0.55) / 1.25, 0.0, 1.0)
            xn_ = hx_ / ws_
            yl_ = (hy_ - 0.68 * (abs(xn_) ** 0.72) + 0.24) / 0.86
            return sqrt(xn_ * xn_ + yl_ * yl_)

        def put_star(rr, cc, ch, f, s_int):
            if rr < 0 or rr >= ROWS or cc < 0 or cc >= COLS:
                return
            u_s = u_min + (cc / (COLS - 1)) * (u_max - u_min)
            v_r = v_min + (rr / (ROWS - 1)) * (v_max - v_min)
            if flight > 0.10 and heart_hr(u_s, v_r) < 0.95:
                return
            k = rr * COLS + cc
            val = s_int * f
            if 0.96 * val > _SP_R[k]:
                _SP_R[k] = 0.96 * val
            if 0.97 * val > _SP_G[k]:
                _SP_G[k] = 0.97 * val
            if val > _SP_B[k]:
                _SP_B[k] = val
            if _STAR_CH[k] == "" or f >= 0.8:
                _STAR_CH[k] = ch

        for sx, sy, sz0, sbright, sphase, ssize in STARS:
            sz = (sz0 - (t * 0.095)) % 1.0
            if sz < 0.04:
                sz = 0.04
            denom = sz * 1.35 + 0.15
            proj_x = sx / denom
            proj_y = sy / denom
            c0 = round(((proj_x - u_min) / (u_max - u_min)) * (COLS - 1))
            r0 = round(((proj_y - v_min) / (v_max - v_min)) * (ROWS - 1))
            if r0 < 0 or r0 >= ROWS or c0 < 0 or c0 >= COLS:
                continue

            twinkle = 0.70 + 0.30 * sin(t * 5.5 + sphase)
            depth_fade = ss(1.0, 0.12, sz) * ss(0.04, 0.10, sz)
            b = sbright * twinkle * depth_fade * space_vis
            if b < 0.14:
                continue

            s_int = min(1.0, b * 1.45)
            if ssize == 0 or sz > 0.68:
                put_star(r0, c0, "." if b < 0.48 else ("+" if b < 0.78 else "*"), 1.0, s_int)
            elif ssize == 1 or (sz < 0.45 and b > 0.55):
                put_star(r0, c0, "*" if b < 0.82 else "@", 1.0, s_int)
                put_star(r0, c0 - 2, ".", 0.45, s_int)
                put_star(r0, c0 - 1, "-", 0.78, s_int)
                put_star(r0, c0 + 1, "-", 0.78, s_int)
                put_star(r0, c0 + 2, ".", 0.45, s_int)
                put_star(r0 - 1, c0, "|", 0.72, s_int)
                put_star(r0 + 1, c0, "|", 0.72, s_int)
            else:
                put_star(r0, c0, "@", 1.0, s_int)
                put_star(r0, c0 - 4, ".", 0.38, s_int)
                put_star(r0, c0 - 3, "-", 0.58, s_int)
                put_star(r0, c0 - 2, "-", 0.78, s_int)
                put_star(r0, c0 - 1, "-", 0.92, s_int)
                put_star(r0, c0 + 1, "-", 0.92, s_int)
                put_star(r0, c0 + 2, "-", 0.78, s_int)
                put_star(r0, c0 + 3, "-", 0.58, s_int)
                put_star(r0, c0 + 4, ".", 0.38, s_int)
                put_star(r0 - 2, c0, ".", 0.45, s_int)
                put_star(r0 - 1, c0, "|", 0.85, s_int)
                put_star(r0 + 1, c0, "|", 0.85, s_int)
                put_star(r0 + 2, c0, ".", 0.45, s_int)

    # --- ASSEMBLE BINARY PPM (P6) IMAGE ---
    get_scan = _SCANLINE_CACHE.get
    chunks = [f"P6 {WIN_W} {WIN_H} 255\n".encode("ascii")]
    row_glyphs = [None] * COLS
    row_ckeys = [0] * COLS

    for r in range(ROWS):
        row_base = r * COLS
        for c in range(COLS):
            idx = row_base + c
            p_mask = clamp(_PM[idx] * space_vis + deep_space, 0.0, 1.0)
            cr = (_EYE_R[idx] * (1.0 - p_mask) + _SP_R[idx] * p_mask) * fade_in
            cg = (_EYE_G[idx] * (1.0 - p_mask) + _SP_G[idx] * p_mask) * fade_in
            cb = (_EYE_B[idx] * (1.0 - p_mask) + _SP_B[idx] * p_mask) * fade_in

            cr = clamp((cr ** 0.74) * 1.18, 0.0, 1.0) if cr > 0.0 else 0.0
            cg = clamp((cg ** 0.74) * 1.18, 0.0, 1.0) if cg > 0.0 else 0.0
            cb = clamp((cb ** 0.74) * 1.18, 0.0, 1.0) if cb > 0.0 else 0.0

            lum = 0.299 * cr + 0.587 * cg + 0.114 * cb
            st_ch = _STAR_CH[idx]
            if p_mask > 0.30 and st_ch != "":
                row_glyphs[c] = GLYPH_MASKS[st_ch]
            else:
                ramp_i = int(lum * (N_RAMP - 1))
                if ramp_i >= N_RAMP:
                    ramp_i = N_RAMP - 1
                row_glyphs[c] = RAMP_GLYPHS[ramp_i]

            r5 = int(cr * 31.0 + 0.5)
            g5 = int(cg * 31.0 + 0.5)
            b5 = int(cb * 31.0 + 0.5)
            row_ckeys[c] = (r5 << 10) | (g5 << 5) | b5

        for y in range(16):
            chunks.append(
                b"".join(
                    get_scan(row_glyphs[c][y] | row_ckeys[c])
                    or _build_scanline(row_glyphs[c][y] | row_ckeys[c])
                    for c in range(COLS)
                )
            )

    return b"".join(chunks)


def run_tkinter_app():
    """Launch the 'Eye -> Space' Tkinter window using 100% built-in standard library Python."""
    import tkinter as tk

    root = tk.Tk()
    root.title("Eye -> Space")
    root.configure(bg="#000000")
    root.resizable(False, False)

    canvas = tk.Canvas(root, width=WIN_W, height=WIN_H, bg="#000000", highlightthickness=0)
    canvas.pack()

    state = {"start": time.perf_counter(), "paused": False, "pause_t": 0.0, "img_ref": None}

    def on_key(event):
        k = event.keysym.lower()
        if k == "escape":
            root.destroy()
        elif k == "r":
            state["start"] = time.perf_counter()
            state["pause_t"] = 0.0
        elif k == "space":
            if state["paused"]:
                state["start"] = time.perf_counter() - state["pause_t"]
                state["paused"] = False
            else:
                state["pause_t"] = time.perf_counter() - state["start"]
                state["paused"] = True

    root.bind("<Key>", on_key)
    root.bind("<Escape>", lambda e: root.destroy())

    img_item = canvas.create_image(0, 0, anchor="nw")

    def tick():
        if state["paused"]:
            t = state["pause_t"]
        else:
            t = (time.perf_counter() - state["start"]) % 15.5

        ppm_data = render_frame_ppm(t)
        tk_im = tk.PhotoImage(width=WIN_W, height=WIN_H, data=ppm_data, format="PPM")
        state["img_ref"] = tk_im
        canvas.itemconfig(img_item, image=tk_im)

        root.after(20, tick)

    tick()
    root.mainloop()


if __name__ == "__main__":
    run_tkinter_app()
