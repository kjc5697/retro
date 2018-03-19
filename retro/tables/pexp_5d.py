# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position

"""
Function to generate the funciton for finding expected number of photons to
survive from a 5D CLSim table.
"""

from __future__ import absolute_import, division, print_function

__all__ = '''
    MACHINE_EPS
    TBL_KIND_CLSIM
    TBL_KIND_CKV
    generate_pexp_5d_function
'''.split()

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

import math
from os.path import abspath, dirname
import sys

import numpy as np

if __name__ == '__main__' and __package__ is None:
    RETRO_DIR = dirname(dirname(dirname(abspath(__file__))))
    if RETRO_DIR not in sys.path:
        sys.path.append(RETRO_DIR)
from retro import DFLT_NUMBA_JIT_KWARGS, numba_jit
from retro.const import PI
from retro.utils.ckv import (
    survival_prob_from_cone, survival_prob_from_smeared_cone
)
from retro.utils.geom import infer_power


MACHINE_EPS = 1e-16

TBL_KIND_CLSIM = 0
TBL_KIND_CKV = 1


def generate_pexp_5d_function(
        table, table_kind, use_directionality, num_phi_samples, ckv_sigma_deg
    ):
    """Generate a numba-compiled function for computing expected photon counts
    at a DOM, where the table's binning info is used to pre-compute various
    constants for the compiled function.

    Parameters
    ----------
    table : mapping
        As returned by `load_clsim_table_minimal`

    table_kind

    use_directionality : bool, optional
        If the source photons have directionality, use it in computing photon
        expectations at the DOM.

    num_phi_samples : int
        Number of samples in the phi_dir to average over bin counts.
        (Irrelevant if `use_directionality` is False.)

    ckv_sigma_deg : float
        Standard deviation in degrees for Cherenkov angle. (Irrelevant if
        `use_directionality` is False).

    Returns
    -------
    pexp_5d : callable
    binning_info : dict
        Binning parameters that uniquely identify the binning from the table.

    """
    r_min = np.min(table['r_bin_edges'])
    # Ensure r_min is zero; this removes need for lower-bound checks and a
    # subtraction
    assert r_min == 0
    r_max = np.max(table['r_bin_edges'])
    rsquared_min = r_min*r_min
    rsquared_max = r_max*r_max
    r_power = infer_power(table['r_bin_edges'])
    inv_r_power = 1 / r_power
    n_r_bins = len(table['r_bin_edges']) - 1
    table_dr_pwr = (r_max - r_min)**inv_r_power / n_r_bins

    n_costheta_bins = len(table['costheta_bin_edges']) - 1
    table_dcostheta = 2 / n_costheta_bins

    t_min = np.min(table['t_bin_edges'])
    # Ensure t_min is zero; this removes need for lower-bound checks and a
    # subtraction
    assert t_min == 0
    t_max = np.max(table['t_bin_edges'])
    n_t_bins = len(table['t_bin_edges']) - 1
    table_dt = (t_max - t_min) / n_t_bins

    assert table['costhetadir_bin_edges'][0] == -1
    assert table['costhetadir_bin_edges'][-1] == 1
    n_costhetadir_bins = len(table['costhetadir_bin_edges']) - 1
    table_dcosthetadir = 2 / n_costhetadir_bins
    assert np.allclose(np.diff(table['costhetadir_bin_edges']), table_dcosthetadir)
    last_costhetadir_bin_idx = n_costhetadir_bins - 1

    assert table['deltaphidir_bin_edges'][0] == 0
    assert np.isclose(table['deltaphidir_bin_edges'][-1], PI)
    n_deltaphidir_bins = len(table['deltaphidir_bin_edges']) - 1
    table_dphidir = PI / n_deltaphidir_bins
    assert np.allclose(np.diff(table['deltaphidir_bin_edges']), table_dphidir)
    last_deltaphidir_bin_idx = n_deltaphidir_bins - 1

    binning_info = dict(
        r_min=r_min, r_max=r_max, n_r_bins=n_r_bins, r_power=r_power,
        n_costheta_bins=n_costheta_bins,
        t_min=t_min, t_max=t_max, n_t_bins=n_t_bins,
        n_costhetadir_bins=n_costhetadir_bins,
        n_deltaphidir_bins=n_deltaphidir_bins,
        deltaphidir_one_sided=True
    )

    random_delta_thetas = np.array([])
    if ckv_sigma_deg > 0:
        rand = np.random.RandomState(0)
        random_delta_thetas = rand.normal(
            loc=0,
            scale=np.deg2rad(ckv_sigma_deg),
            size=num_phi_samples
        )

    @numba_jit(**DFLT_NUMBA_JIT_KWARGS)
    def pexp_5d(
            pinfo_gen, hit_time, time_window, dom_coord, quantum_efficiency,
            noise_rate_hz, table, table_norm#, t_indep_table, t_indep_table_norm
        ):
        """For a set of generated photons `pinfo_gen`, compute the expected
        photons in a particular DOM at `hit_time` and the total expected
        photons, independent of time.

        This function utilizes the relative space-time coordinates _and_
        directionality of the generated photons (via "raw" 5D CLSim tables) to
        determine how many photons are expected to arrive at the DOM.

        Retro DOM tables applied to the generated photon info `pinfo_gen`,
        and the total expected photon count (time integrated) -- the
        normalization of the pdf.

        Parameters
        ----------
        pinfo_gen : shape (N, 8) ndarray
            Information about the photons generated by the hypothesis.

        hit_time : float, units of ns
            Time at which the DOM recorded a hit (or multiple simultaneous
            hits). Use np.nan to indicate no hit occurred.

        time_window : float, units of ns
            The entire tine window of data considered, used to arrive at
            expected total noise hits (along with `noise_rate_hz`).

        dom_coord : shape (3,) ndarray
            DOM (x, y, z) coordinate in meters (in terms of the IceCube
            coordinate system).

        quantum_efficiency : float in (0, 1]
            Scale factor that reduces detected photons due to average quantum
            efficiency of the DOM.

        noise_rate_hz : float
            Noise rate for the DOM, in Hz.

        table : shape (n_r, n_costheta, n_t, n_costhetadir, n_deltaphidir) ndarray
            Time-dependent photon survival probability table.

        table_norm : shape (n_r, n_t) ndarray
            Normalization to apply to `table`, which is assumed to depend on
            both r- and t-dimensions and therefore is an array.

        t_indep_table : shape (n_r, n_costheta, n_costhetadir, n_deltaphidir) ndarray
            Time-independent photon survival probability table.

        t_indep_table_norm : float
            r- and t-dependent normalization is assumed to already have been
            applied to generate the t_indep_table, leaving only a possible
            constant normalization that must still be applied (e.g.
            ``quantum_efficiency*angular_acceptance_fract``).

        Returns
        -------
        photons_at_all_times : float
            Total photons due to the hypothesis expected to arrive at the
            specified DOM for _all_ times.

        photons_at_hit_time : float
            Total photons due to the hypothesis expected to arrive at the
            specified DOM at the time the DOM recorded the hit.

        """
        # NOTE: on optimization:
        # * np.square(x) is slower than x*x by a few percent (maybe within tolerance, though)

        # Initialize accumulators (using double precision)

        photons_at_all_times = np.float64(0.0)
        photons_at_hit_time = np.float64(0.0)

        # Initialize "prev_*" vars

        prev_r_bin_idx = -1
        prev_costheta_bin_idx = -1
        prev_t_bin_idx = -1
        prev_costhetadir_bin_idx = -1
        prev_deltaphidir_bin_idx = -1
        if use_directionality:
            prev_pdir_r = np.nan
        else:
            pdir_r = 0.0
            new_pdir_r = False

        # Initialize cached values to nan since it's a bug if these are not
        # computed at least the first time through and this will help ensure
        # that such a bug shows itself

        this_table_norm = np.nan

        # Loop over the entries (one per row)

        for pgen_idx in range(pinfo_gen.shape[0]):
            # Info about the generated photons
            t, x, y, z, p_count, pdir_x, pdir_y, pdir_z = pinfo_gen[pgen_idx, :]

            #print('t={}, x={}, y={}, z={}, p_count={}, pdir_x={}, pdir_y={}, pdir_z={}'
            #      .format(t, x, y, z, p_count, pdir_x, pdir_y, pdir_z))

            # A photon that starts immediately in the past (before the DOM was hit)
            # will show up in the raw CLSim Retro DOM tables in bin 0; the
            # further in the past the photon started, the higher the time bin
            # index.
            dt = hit_time - t
            dx = dom_coord[0] - x
            dy = dom_coord[1] - y
            dz = dom_coord[2] - z

            #print('dt={}, dx={}, dy={}, dz={}'.format(dt, dx, dy, dz))

            rhosquared = dx*dx + dy*dy
            rsquared = rhosquared + dz*dz

            # Continue if photon is outside the radial binning limits
            if rsquared >= rsquared_max or rsquared < rsquared_min:
                #print('XX CONTINUE: outside r binning')
                continue

            r = math.sqrt(rsquared)
            r_bin_idx = int(r**inv_r_power // table_dr_pwr)
            costheta_bin_idx = int((1 - dz/r) // table_dcostheta)

            #print('r={}, r_bin_idx={}, costheta_bin_idx={}'.format(r, r_bin_idx, costheta_bin_idx))

            if r_bin_idx == prev_r_bin_idx:
                new_r_bin = False
            else:
                new_r_bin = True
                prev_r_bin_idx = r_bin_idx

            if costheta_bin_idx == prev_costheta_bin_idx:
                new_costheta_bin = False
            else:
                new_costheta_bin = True
                prev_costheta_bin_idx = costheta_bin_idx

            if use_directionality:
                pdir_rhosquared = pdir_x*pdir_x + pdir_y*pdir_y
                pdir_r = math.sqrt(pdir_rhosquared + pdir_z*pdir_z)

                #print('pdir_rhosquared={}, pdir_r={}'.format(pdir_rhosquared, pdir_r))

                if pdir_r != prev_pdir_r:
                    new_pdir_r = True
                    prev_pdir_r = pdir_r
                else:
                    new_pdir_r = False

            # TODO: handle special cases for pdir_r:
            #
            #   pdir_r == 1 : Line emitter
            #   pdir_r  > 1 : Gaussian profile with stddev (pdir_r - 1)
            #
            # Note that while pdir_r == 1 is a special case of both Cherenkov
            # emission and Gaussian-profile emission, both of those are very
            # computationally expensive compared to a simple
            # perfectly-directional source, so we should handle all three
            # separately.

            if pdir_r == 0.0: # isotropic emitter
                pass
                #if new_pdir_r or new_r_bin or new_costheta_bin:
                #    this_photons_at_all_times = np.mean(
                #        t_indep_table[r_bin_idx, costheta_bin_idx, :, :]
                #    )

            elif pdir_r < 1.0: # Cherenkov emitter
                # Note that for these tables, we have to invert the photon
                # direction relative to the vector from the DOM to the photon's
                # vertex since simulation has photons going _away_ from the DOM
                # that in reconstruction will hit the DOM if they're moving
                # _towards_ the DOM.

                pdir_rho = math.sqrt(pdir_rhosquared)

                # Zenith angle is indep. of photon position relative to DOM
                pdir_costheta = pdir_z / pdir_r
                pdir_sintheta = pdir_rho / pdir_r

                rho = math.sqrt(rhosquared)

                # \Delta\phi depends on photon position relative to the DOM...

                # Below is the projection of pdir into the (x, y) plane and the
                # projection of that onto the vector in that plane connecting
                # the photon source to the DOM. We get the cosine of the angle
                # between these vectors by solving the identity
                #   `a dot b = |a| |b| cos(deltaphi)`
                # for cos(deltaphi).
                #
                if pdir_rho <= MACHINE_EPS or rho <= MACHINE_EPS:
                    pdir_cosdeltaphi = 1.0
                    pdir_sindeltaphi = 0.0
                else:
                    pdir_cosdeltaphi = (
                        pdir_x/pdir_rho * dx/rho + pdir_y/pdir_rho * dy/rho
                    )
                    # Note that the max and min here here in case numerical
                    # precision issues cause the dot product to blow up.
                    pdir_cosdeltaphi = min(1, max(-1, pdir_cosdeltaphi))
                    pdir_sindeltaphi = math.sqrt(1 - pdir_cosdeltaphi * pdir_cosdeltaphi)

                #print('pdir_cosdeltaphi={}, pdir_sindeltaphi={}'
                #      .format(pdir_cosdeltaphi, pdir_sindeltaphi))

                # Cherenkov angle is encoded as the projection of a length-1
                # vector going in the Ckv direction onto the charged particle's
                # direction. Ergo, in the length of the pdir vector is the
                # cosine of the ckv angle.
                ckv_costheta = pdir_r
                ckv_theta = math.acos(ckv_costheta)

                #print('ckv_theta={}'.format(ckv_theta*180/PI))

                if table_kind == TBL_KIND_CLSIM:
                    if ckv_sigma_deg > 0:
                        pass
                        #this_photons_at_all_times, _a, _b = survival_prob_from_smeared_cone( # pylint: disable=unused-variable, invalid-name
                        #    theta=ckv_theta,
                        #    num_phi=num_phi_samples,
                        #    rot_costheta=pdir_costheta,
                        #    rot_sintheta=pdir_sintheta,
                        #    rot_cosphi=pdir_cosdeltaphi,
                        #    rot_sinphi=pdir_sindeltaphi,
                        #    directional_survival_prob=(
                        #        t_indep_table[r_bin_idx, costheta_bin_idx, :, :]
                        #    ),
                        #    num_costheta_bins=n_costhetadir_bins,
                        #    num_deltaphi_bins=n_deltaphidir_bins,
                        #    random_delta_thetas=random_delta_thetas
                        #)
                    else:
                        ckv_sintheta = math.sqrt(1 - ckv_costheta*ckv_costheta)
                        #this_photons_at_all_times, _a, _b = survival_prob_from_cone( # pylint: disable=unused-variable, invalid-name
                        #    costheta=ckv_costheta,
                        #    sintheta=ckv_sintheta,
                        #    num_phi=num_phi_samples,
                        #    rot_costheta=pdir_costheta,
                        #    rot_sintheta=pdir_sintheta,
                        #    rot_cosphi=pdir_cosdeltaphi,
                        #    rot_sinphi=pdir_sindeltaphi,
                        #    directional_survival_prob=(
                        #        t_indep_table[r_bin_idx, costheta_bin_idx, :, :]
                        #    ),
                        #    num_costheta_bins=n_costhetadir_bins,
                        #    num_deltaphi_bins=n_deltaphidir_bins,
                        #)

                elif table_kind == TBL_KIND_CKV:
                    costhetadir_bin_idx = int((pdir_costheta + 1) // table_dcosthetadir)
                    # Make upper edge inclusive
                    if costhetadir_bin_idx > last_costhetadir_bin_idx:
                        costhetadir_bin_idx = last_costhetadir_bin_idx

                    if costhetadir_bin_idx == prev_costhetadir_bin_idx:
                        new_costhetadir_bin = False
                    else:
                        new_costhetadir_bin = True
                        prev_costhetadir_bin_idx = costhetadir_bin_idx

                    pdir_deltaphi = math.acos(pdir_cosdeltaphi)
                    deltaphidir_bin_idx = int(pdir_deltaphi // table_dphidir)
                    # Make upper edge inclusive
                    if deltaphidir_bin_idx > last_deltaphidir_bin_idx:
                        deltaphidir_bin_idx = last_deltaphidir_bin_idx

                    if deltaphidir_bin_idx == prev_deltaphidir_bin_idx:
                        new_deltaphidir_bin = False
                    else:
                        new_deltaphidir_bin = True
                        prev_deltaphidir_bin_idx = deltaphidir_bin_idx

                    if new_r_bin or new_costheta_bin or new_costhetadir_bin or new_deltaphidir_bin:
                        new_r_ct_ctd_or_dpd_bin = True
                        #this_photons_at_all_times = t_indep_table[r_bin_idx, costheta_bin_idx, costhetadir_bin_idx, deltaphidir_bin_idx]
                    else:
                        new_r_ct_ctd_or_dpd_bin = False
                else:
                    raise ValueError('Unknown table kind.')

            elif pdir_r == 1.0: # line emitter; can't do this with Ckv table!
                raise NotImplementedError('Line emitter not handled.')

            else: # Gaussian emitter; can't do this with Ckv table!
                raise NotImplementedError('Gaussian emitter not handled.')

            #photons_at_all_times += p_count * t_indep_table_norm * this_photons_at_all_times

            #print('photons_at_all_times={}'.format(photons_at_all_times))

            # Causally impossible? (Note the comparison is written such that it
            # will evaluate to True if hit_time is NaN.)
            if not t <= hit_time:
                #print('XX CONTINUE: noncausal')
                continue

            # Is relative time outside binning?
            if dt >= t_max:
                #print('XX CONTINUE: outside t binning')
                continue

            t_bin_idx = int(dt // table_dt)

            #print('t_bin_idx={}'.format(t_bin_idx))

            if t_bin_idx == prev_t_bin_idx:
                new_t_bin = False
            else:
                new_t_bin = True
                prev_t_bin_idx = t_bin_idx

            if new_r_bin or new_t_bin:
                this_table_norm = table_norm[r_bin_idx, t_bin_idx]

            if pdir_r == 0.0: # isotropic emitter
                if new_pdir_r or new_r_bin or new_costheta_bin or new_t_bin:
                    this_photons_at_hit_time = np.mean(
                        table[r_bin_idx, costheta_bin_idx, t_bin_idx, :, :]
                    )
            elif pdir_r < 1.0: # Cherenkov emitter
                if table_kind == TBL_KIND_CLSIM:
                    if ckv_sigma_deg > 0:
                        this_photons_at_hit_time, _c, _d = survival_prob_from_smeared_cone( # pylint: disable=unused-variable, invalid-name
                            theta=ckv_theta,
                            num_phi=num_phi_samples,
                            rot_costheta=pdir_costheta,
                            rot_sintheta=pdir_sintheta,
                            rot_cosphi=pdir_cosdeltaphi,
                            rot_sinphi=pdir_sindeltaphi,
                            directional_survival_prob=(
                                table[r_bin_idx, costheta_bin_idx, t_bin_idx, :, :]
                            ),
                            num_costheta_bins=n_costhetadir_bins,
                            num_deltaphi_bins=n_deltaphidir_bins,
                            random_delta_thetas=random_delta_thetas
                        )
                    else:
                        this_photons_at_hit_time, _c, _d = survival_prob_from_cone( # pylint: disable=unused-variable, invalid-name
                            costheta=ckv_costheta,
                            sintheta=ckv_sintheta,
                            num_phi=num_phi_samples,
                            rot_costheta=pdir_costheta,
                            rot_sintheta=pdir_sintheta,
                            rot_cosphi=pdir_cosdeltaphi,
                            rot_sinphi=pdir_sindeltaphi,
                            directional_survival_prob=(
                                table[r_bin_idx, costheta_bin_idx, t_bin_idx, :, :]
                            ),
                            num_costheta_bins=n_costhetadir_bins,
                            num_deltaphi_bins=n_deltaphidir_bins,
                        )
                    #print('this_photons_at_hit_time={}'.format(this_photons_at_hit_time))
                elif table_kind == TBL_KIND_CKV:
                    if new_r_ct_ctd_or_dpd_bin or new_t_bin:
                        this_photons_at_hit_time = table[r_bin_idx, costheta_bin_idx, t_bin_idx, costhetadir_bin_idx, deltaphidir_bin_idx]

            elif pdir_r == 1.0: # line emitter
                raise NotImplementedError('Line emitter not handled.')
            else: # Gaussian emitter
                raise NotImplementedError('Gaussian emitter not handled.')

            photons_at_hit_time += p_count * this_table_norm * this_photons_at_hit_time
            #print('photons_at_hit_time={}'.format(photons_at_hit_time))
            #print('XX FINISHED LOOP')

        photons_at_all_times = quantum_efficiency * photons_at_all_times + noise_rate_hz * time_window * 1e-9
        photons_at_hit_time = quantum_efficiency * photons_at_hit_time + noise_rate_hz * table_dt * 1e-9

        return photons_at_all_times, photons_at_hit_time

    return pexp_5d, binning_info
