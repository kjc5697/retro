# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position

"""
Discrete-time kernels for cascades generating photons, to be used as
hypo_kernels in discrete_hypo/DiscreteHypo class.
"""

from __future__ import absolute_import, division, print_function

__all__ = ['point_cascade']

__author__ = 'P. Eller, J.L. Lanfranchi'
__license__ = '''Copyright 2017 Philipp Eller and Justin L. Lanfranchi

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.'''

from os.path import abspath, dirname
import sys

import numpy as np

if __name__ == '__main__' and __package__ is None:
    RETRO_DIR = dirname(dirname(dirname(abspath(__file__))))
    if RETRO_DIR not in sys.path:
        sys.path.append(RETRO_DIR)
from retro import numba_jit, DFLT_NUMBA_JIT_KWARGS
from retro.const import CASCADE_PHOTONS_PER_GEV
from retro.hypo.discrete_hypo import SRC_DTYPE, SRC_OMNI


@numba_jit(**DFLT_NUMBA_JIT_KWARGS)
def point_cascade(hypo_params):
    """Point-like cascade.

    Use as a hypo_kernel with the DiscreteHypo class.

    Parameters
    ----------
    hypo_params : HypoParams8D or HypoParams10D

    Returns
    -------
    sources

    """
    sources = np.empty(shape=(1,), dtype=SRC_DTYPE)
    sources[0]['kind'] = SRC_OMNI
    sources[0]['t'] = hypo_params.t
    sources[0]['x'] = hypo_params.x
    sources[0]['y'] = hypo_params.y
    sources[0]['z'] = hypo_params.z
    sources[0]['photons'] = CASCADE_PHOTONS_PER_GEV * hypo_params.cascade_energy
    sources[0]['dir_x'] = 0
    sources[0]['dir_y'] = 0
    sources[0]['dir_z'] = 0
    #    [(
    #        SRC_OMNI,
    #        hypo_params.t,
    #        hypo_params.x,
    #        hypo_params.y,
    #        hypo_params.z,
    #        CASCADE_PHOTONS_PER_GEV * hypo_params.cascade_energy,
    #        0.0,
    #        0.0,
    #        0.0
    #    )],
    #    dtype=SRC_DTYPE
    #)
    return sources
