# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position

"""
Generate single-DOM Retro tables binned in (t,r,theta), with each bin
containing a survival probability and average directionality vector. The length
of this vector indicates "how directional" light is, from 0 (isotropic) to 1
(perfectly directional). The information provided comes from the single-DOM
Retro tables generated by CLSim, which are binned in
(theta,r,t,theta_dir,deltaphi_dir).
"""

from __future__ import absolute_import, division, print_function

__all__ = ['generate_t_r_theta_table']

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
    PARENT_DIR = dirname(dirname(abspath(__file__)))
    if PARENT_DIR not in sys.path:
        sys.path.append(PARENT_DIR)
from retro import DFLT_NUMBA_JIT_KWARGS, numba_jit
from retro.const import SPEED_OF_LIGHT_M_PER_NS
from retro.utils.stats import weighted_average


@numba_jit(**DFLT_NUMBA_JIT_KWARGS)
def generate_t_r_theta_table(
        table,
        n_photons,
        group_refractive_index,
        t_bin_width,
        angular_acceptance_fract,
        thetadir_centers,
        deltaphidir_centers,
        theta_bin_edges
    ):
    """Transform information from a raw single-DOM table (as output from CLSim)
    that is binned in (r, theta, t, theta_dir, deltaphi_dir) into a more
    compact representation, with a probability and an average direction vector
    (represented by a single theta and phi) in each (t, r, theta) bin.

    Parameters
    ----------
    table
    n_photons
    group_refractive_index
    t_bin_width
    angular_acceptance_fract
    thetadir_centers
    deltaphidir_centers
    theta_bin_edges

    Returns
    -------
    survival_probs
    average_thetas
    average_phis
    lengths

    """
    # Source tables are photon counts binned in
    # (r, theta, t, dir_theta, dir_phi)
    n_r_bins = table.shape[0]
    n_theta_bins = table.shape[1]
    n_t_bins = table.shape[2]

    # (Base) survival probability (that will be modified by directionality):
    # We can either
    # 1. Sum over the directionality dimensions, which means "probability that
    #    photon is going in any one of these directions is P_{det, tot}. This
    #    is like the total area under a curve, but then we have to distribute
    #    this total area among all the directions via the distribution we
    #    parameterize as fn of dir vector length."
    # 2. Max over directionality dimensions, which means "the best P_det occurs
    #    if the photon is moving in this particular direction, whereupon it
    #    will be detected with P_{det, max}. It gets worse from there according
    #    to the distribution we parameterize as fn of dir vector length."

    norm = (
        1
        / n_photons
        / (SPEED_OF_LIGHT_M_PER_NS / group_refractive_index)
        / t_bin_width
        * angular_acceptance_fract
        * n_theta_bins
    )

    # Destination tables are to be binned in (t, r, costheta) (there are as
    # many costheta bins as theta bins in the original tables)
    dest_shape = (n_t_bins, n_r_bins, n_theta_bins)

    survival_probs = np.empty(dest_shape, dtype=np.float32)
    average_thetas = np.empty(dest_shape, dtype=np.float32)
    average_phis = np.empty(dest_shape, dtype=np.float32)
    lengths = np.empty(dest_shape, dtype=np.float32)

    for r_i in range(n_r_bins):
        for theta_j in range(n_theta_bins):
            for t_k in range(n_t_bins):
                # flip coszen_dir (photon direction)
                weights = table[r_i, theta_j, t_k, ::-1, :].astype(np.float64)
                weights_tot = weights.sum()
                if weights_tot == 0:
                    # If no photons, just set the average direction to the
                    # theta of the bin center...
                    average_theta = 0.5 * (theta_bin_edges[theta_j]
                                           + theta_bin_edges[theta_j + 1])
                    # ... and lengths to 0
                    length = 0.0
                    average_phi = 0.0
                else:
                    # Average theta
                    weights_theta = weights.sum(axis=1)
                    average_theta = weighted_average(thetadir_centers,
                                                     weights_theta)

                    # Average delta phi
                    projected_survival_prob = (
                        (weights.T * np.sin(thetadir_centers)).T
                    )
                    weights_phi = projected_survival_prob.sum(axis=0)
                    average_phi = weighted_average(deltaphidir_centers,
                                                   weights_phi)

                    # Length of vector (using projections from all vectors
                    # onto average vector cos(angle) between average vector
                    # and all angles)
                    coscos = np.cos(thetadir_centers)*np.cos(average_theta)
                    sinsin = np.sin(thetadir_centers)*np.sin(average_theta)
                    cosphi = np.cos(deltaphidir_centers - average_phi)
                    # Other half of sphere
                    cospsi = (coscos + np.outer(sinsin, cosphi).T).T
                    cospsi_avg = (cospsi * weights).sum() / weights_tot
                    length = max(0.0, 2 * (cospsi_avg - 0.5))

                # Output tables are expected to be in (flip(t), r, costheta).
                # In addition to time being flipped, coszen is expected to be
                # ascending, and therefore its binning is also flipped as
                # compared to the theta binning in the original table.
                dest_bin = (
                    n_t_bins - 1 - t_k,
                    r_i,
                    n_theta_bins - 1 - theta_j
                )

                survival_probs[dest_bin] = norm * table[r_i, theta_j, t_k]
                average_thetas[dest_bin] = average_theta
                average_phis[dest_bin] = average_phi
                lengths[dest_bin] = length

    return survival_probs, average_thetas, average_phis, lengths
