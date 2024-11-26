import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import concurrent.futures
from enum import Enum
from io import BytesIO
import math
from pathlib import Path
from typing import Literal, Sequence
from cachetools import LRUCache, TTLCache, cached
import concurrent
from discord import Colour
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from draftphase.game import Offer
from draftphase.maps import Environment, Faction, MapDetails, LayoutType, Orientation

IM_SIZE = 400
IM_STACK_GAP_SIZE = int(0.1 * IM_SIZE)
OBJECTIVE_LINE_THICKNESS = int(0.025 * IM_SIZE)
PLACEHOLDER_ROUND_RADIUS = int(0.15 * IM_SIZE)

ARIAL_BOLD_TTF = Path("assets/fonts/Arial Bold.ttf")

class Colors(Enum):
    OBJECTIVE_LINE = Colour(0x11e72b).to_rgb()
    PLACEHOLDER_BG = Colour(0x202225).to_rgb()
    PLACEHOLDER_TEXT = Colour(0x414347).to_rgb()

def open_tacmap(details: MapDetails):
    im = Image.open(details.tacmap)
    return im

def open_faction(faction: Faction, selected: bool = False):
    fn = faction.value
    if selected:
        fn += "_selected"
    im = Image.open(Path(f"assets/factions/{fn}.png"))
    return im

def open_environment(environment: Environment):
    im = Image.open(Path(f"assets/environments/{environment.value}.png"))
    return im

def draw_layout(im: Image.Image, layout: LayoutType, orientation: Orientation):
    draw = ImageDraw.Draw(im)
    do_flip = orientation == Orientation.VERTICAL

    def get_y(p: int):
        return (p + 1.5) * line_width * 2

    line_width = IM_SIZE / (5 * 2)
    x = x_old = line_width / -2
    y = y_old = get_y(layout[0])
    
    points = [layout[0], *layout, layout[-1], layout[-1]]
    for p in points:
        x_old = x
        y_old = y
        x += line_width
        y = get_y(p)
        draw.circle(
            (y, x) if do_flip else (x, y),
            radius=(OBJECTIVE_LINE_THICKNESS / 2) - 1,
            fill=Colors.OBJECTIVE_LINE.value
        )
        draw.line(
            (y_old, x_old, y, x) if do_flip else (x_old, y_old, x, y),
            fill=Colors.OBJECTIVE_LINE.value,
            width=OBJECTIVE_LINE_THICKNESS
        )
        
        x_old = x
        y_old = y
        x += line_width
        draw.circle(
            (y, x) if do_flip else (x, y),
            radius=(OBJECTIVE_LINE_THICKNESS / 2) - 1,
            fill=Colors.OBJECTIVE_LINE.value
        )
        draw.line(
            (y_old, x_old, y, x) if do_flip else (x_old, y_old, x, y),
            fill=Colors.OBJECTIVE_LINE.value,
            width=OBJECTIVE_LINE_THICKNESS
        )

        # Draw strongpoints
        # draw.circle(
        #     (y, x-(line_width/2)) if do_flip else (x-(line_width/2), y),
        #     radius=(OBJECTIVE_LINE_THICKNESS / 2) + 10,
        #     fill=Colors.OBJECTIVE_LINE.value,
        # )
    
    return im

def draw_factions(
    im: Image.Image,
    details: MapDetails,
    selected_team_id: Literal[1] | Literal[2] | None = None,
    spaced: bool = False
):
    f_size = int(IM_SIZE / 4)
    im_allies = open_faction(details.allies, selected=(selected_team_id == 1)).resize(
        (f_size, f_size),
        resample=Image.Resampling.BICUBIC,
    )
    im_axis = open_faction(details.axis, selected=(selected_team_id == 2)).resize(
        (f_size, f_size),
        resample=Image.Resampling.BICUBIC,
    )

    ims = [im_allies, im_axis]
    if details.flip_sides:
        ims = ims[::-1]

    if details.orientation == Orientation.HORIZONTAL:
        im_axis_coords = (
            0,
            IM_SIZE - f_size,
        )
        im_allies_coords = (
            (IM_SIZE - f_size) if spaced else f_size,
            IM_SIZE - f_size,
        )
    else:
        im_axis_coords = (
            IM_SIZE - f_size,
            0,
        )
        im_allies_coords = (
            IM_SIZE - f_size,
            (IM_SIZE - f_size) if spaced else f_size,
        )

    im.paste(ims[0], im_allies_coords, mask=ims[0])
    im.paste(ims[1], im_axis_coords, mask=ims[1])

    return im

def draw_environment(im: Image.Image, environment: Environment):
    im_size = int(IM_SIZE / 5)
    im_environment = open_environment(environment).resize(
        (im_size, im_size),
        resample=Image.Resampling.BICUBIC,
    )
    im.paste(
        im_environment,
        (im_size * 4, im_size * 4),
        mask=im_environment,
    )
    return im

def draw_map_name(im: Image.Image, name: str, orientation: Orientation):
    canvas = Image.new(mode="RGBA", size=(IM_SIZE, IM_SIZE // 5))
    draw = ImageDraw.Draw(canvas)

    font = ImageFont.truetype(ARIAL_BOLD_TTF, size=57 / 400 * IM_SIZE)
    dx0, dy0, dx1, dy1 = draw.textbbox((0, 0), text=name, font=font)
    draw.text(
        (
            (IM_SIZE - dx0 - dx1) / 2,
            (IM_SIZE / 5 - dy0 - dy1) / 2,
        ),
        text=name,
        fill="white",
        font=font,
    )
    
    if orientation == Orientation.VERTICAL:
        canvas = canvas.transpose(Image.Transpose.ROTATE_90)
    
    im.paste(canvas, mask=canvas)


@cached(LRUCache(10))
def get_placeholder(num: int = 1):
    im = Image.new(mode="RGBA", size=(IM_SIZE, IM_SIZE))
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle(
        (0, 0, IM_SIZE, IM_SIZE),
        radius=60,
        fill=Colors.PLACEHOLDER_BG.value,
    )

    if num > 1:
        text = f"+{num}"
        font = ImageFont.truetype(ARIAL_BOLD_TTF, size=0.5 * IM_SIZE)
        dx0, dy0, dx1, dy1 = draw.textbbox((0, 0), text=text, font=font)
        draw.text(
            (
                (IM_SIZE - dx0 - dx1) / 2 - (0.02 * IM_SIZE),
                (IM_SIZE - dy0 - dy1) / 2,
            ),
            text=text,
            fill=Colors.PLACEHOLDER_TEXT.value,
            font=font,
        )

    return im

@cached(cache=LRUCache(maxsize=100))
def get_map_image(
    details: MapDetails,
    layout: LayoutType | None,
    environment: Environment | None,
    selected_team_id: Literal[1, 2] | None
):
    im = open_tacmap(details)
    draw_factions(im, details, selected_team_id=selected_team_id)
    draw_map_name(im, details.short_name, details.orientation)

    if layout:
        draw_layout(im, layout, details.orientation)

    if environment:
        draw_environment(im, environment)

    return im

def stack_in_rows(ims: Sequence[Image.Image], maxsize: int = 6, rowsize: int = 3, grayscaled: bool = False):
    if len(ims) > maxsize:
        raise ValueError("Amount of images exceeds max size")
    
    num_ims = len(ims) + 1
    num_ims += ((rowsize - num_ims) % rowsize)
    num_ims = min(num_ims, maxsize)
        
    dist = IM_SIZE + IM_STACK_GAP_SIZE
    
    num_rows = math.ceil(num_ims / rowsize)
    canvas = Image.new(
        mode="RGBA",
        size=(
            (dist*rowsize) - IM_STACK_GAP_SIZE,
            (dist*num_rows) - IM_STACK_GAP_SIZE,
        ),
    )

    placeholder = get_placeholder()

    row = 0
    col = -1
    for i in range(num_ims):
        if i < len(ims):
            im = ims[i]
            if grayscaled:
                im = get_grayscale(im)
        elif i + 1 == num_ims:
            num = 1 + maxsize - num_ims
            im = get_placeholder(num=num)
        else:
            im = placeholder

        col += 1
        if col >= rowsize:
            row += 1
            col = 0
        
        canvas.paste(im, (col*dist, row*dist))

    return canvas

def get_grayscale(im: Image.Image):
    # im = im.convert("LA")
    im = ImageEnhance.Color(im).enhance(0.2)
    return im


def offers_to_image_sync(offers: Sequence['Offer'], max_num_offers: int, grayscaled: bool = False, flip_sides: bool = False):
    # Process individual images inside of a thread pool
    pool = ThreadPoolExecutor()
    futs: list[Future] = []
    for offer in offers:
        fut = pool.submit(
            get_map_image,
            details=offer.get_map_details(),
            layout=offer.layout,
            environment=offer.environment,
            selected_team_id=(1 if flip_sides == bool(offer.offer_no % 2) else 2) if offer.accepted else None,
        )
        futs.append(fut)

    # Wait for all futures to complete, then close the pool to free resources
    pool.shutdown(wait=True)
    ims = [fut.result() for fut in futs]

    # Combine the individual images
    im = stack_in_rows(ims, maxsize=max_num_offers, grayscaled=grayscaled)

    fp = BytesIO()
    im.save(fp, "png")
    fp.seek(0)
    return fp

async def offers_to_image(offers: Sequence['Offer'], max_num_offers: int, grayscaled: bool = False, flip_sides: bool = False):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, offers_to_image_sync, offers, max_num_offers, grayscaled
    )

def get_single_offer_image_sync(
    details: MapDetails | None = None,
    layout: LayoutType | None = None,
    environment: Environment | None = None,
    selected_team_id: Literal[1, 2] | None = None,
):
    if details:
        im = get_map_image(
            details=details,
            layout=layout,
            environment=environment,
            selected_team_id=selected_team_id,
        )
    else:
        im = get_placeholder()
    fp = BytesIO()
    im.save(fp, "png")
    fp.seek(0)
    return fp

async def get_single_offer_image(
    details: MapDetails | None = None,
    layout: LayoutType | None = None,
    environment: Environment | None = None,
    selected_team_id: Literal[1, 2] | None = None,
):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, get_single_offer_image_sync,
        details, layout, environment, selected_team_id
    )
