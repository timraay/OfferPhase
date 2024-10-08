from enum import Enum
from PIL import Image, ImageDraw
from discord import Colour

from draftphase.maps import get_all_layout_combinations

class Colors(Enum):
    BORDER = Colour(0x4c4642).to_rgb()
    BACKGROUND_NEUTRAL = Colour(0x918275).to_rgb()
    BACKGROUND_BLUE = Colour(0x809c9c).to_rgb()
    BACKGROUND_RED = Colour(0x8e6d6d).to_rgb()
    OBJECTIVE = Colour(0x32f11f).to_rgb()


def main():
    im = Image.new(mode="RGB", size=(5,5), color=Colors.BORDER.value)
    draw = ImageDraw.Draw(im)

    draw.rectangle((1, 0, 3, 1), fill=Colors.BACKGROUND_BLUE.value)
    draw.rectangle((1, 2, 3, 2), fill=Colors.BACKGROUND_NEUTRAL.value)
    draw.rectangle((1, 3, 3, 4), fill=Colors.BACKGROUND_RED.value)

    for layout in get_all_layout_combinations():
        im2 = im.copy()
        for row, obj in enumerate(layout, 1):
            im2.putpixel((obj+1, row), Colors.OBJECTIVE.value)
        
        im_name = "assets\\emojis\\obj_vert_" + "".join([str(i) for i in layout]) + ".png"
        (
            im2
            .resize(size=(500, 500), resample=Image.Resampling.NEAREST)
            .save(im_name, format="png")
        )

        im_name = "assets\\emojis\\obj_hor_" + "".join([str(i) for i in layout]) + ".png"
        (
            im2
            .transpose(Image.Transpose.ROTATE_90)
            .transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            .resize(size=(500, 500), resample=Image.Resampling.NEAREST)
            .save(im_name, format="png")
        )

if __name__ == '__main__':
    main()