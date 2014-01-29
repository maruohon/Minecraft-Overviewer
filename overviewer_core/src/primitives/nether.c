/* 
 * This file is part of the Minecraft Overviewer.
 *
 * Minecraft Overviewer is free software: you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as published
 * by the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * Minecraft Overviewer is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 * Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with the Overviewer.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "../overviewer.h"
#include "nether.h"

static void
walk_chunk(RenderState *state, RenderPrimitiveNether *data) {
    int x, y, z;
    int id;

    for (x = -1; x < WIDTH + 1; x++) {
        for (z = -1; z < DEPTH + 1; z++) {
            id = get_data(state, BLOCKS, x, NETHER_ROOF - (state->chunky * 16), z);
            if (id == 7) {
                data->remove_block[x+1][NETHER_ROOF][z+1] = 1;
                id = get_data(state, BLOCKS, x, (NETHER_ROOF + 1) - (state->chunky * 16), z);
                if (id == 39 || id == 40)
                    data->remove_block[x+1][NETHER_ROOF + 1][z+1] = 1;
            }

            for (y = NETHER_ROOF-1; y>=0; y--) {
                id = get_data(state, BLOCKS, x, y - (state->chunky * 16), z);
                /* 7 = Bedrock; 11 = Lava (still); 87 == Netherrack;
                88 = Soul Sand; 153 == Nether Quartz Ore */
                /* BoP: Ash Block (I:"Ash Block ID"=163) */
                /* Natura: Tainted Soil (I:"Tainted Soil"=169) */
                /* Tinker's Construct: Ores (I:"Ores Slag"=1475), data = 1: Cobalt Ore, data = 2: Ardite Ore,
                but we don't need to check the data value, since the others are overworld-only */
                /* Magic Bees: Hives (I:hives=1754), data = 4: Infernal Hive */
                /* Dartcraft: Power Ore (I:"Power Ore"=1900), data = 1 is the nether variant,
                although we don't need to check for that */
                if (id == 7 || id == 11 || id == 87 || id == 88 || id == 153 ||
                    id == 163 || id == 169 || id == 1475 || id == 1754 || id == 1900)
                    data->remove_block[x+1][y][z+1] = 1;
                else
                    break;
            }
        }
    }
    data->walked_chunk = 1;
}

static int
nether_hidden(void *data, RenderState *state, int x, int y, int z) {
    RenderPrimitiveNether* self;
    int real_y;

    self = (RenderPrimitiveNether *)data;

    if (!(self->walked_chunk))
        walk_chunk(state, self);

    real_y = y + (state->chunky * 16);
    return self->remove_block[x+1][real_y][z+1];
}

RenderPrimitiveInterface primitive_nether = {
    "nether", sizeof(RenderPrimitiveNether),
    NULL,
    NULL,
    NULL,
    nether_hidden,
    NULL,
};
