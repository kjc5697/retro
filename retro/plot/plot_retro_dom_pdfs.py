#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pylint: disable=wrong-import-position

"""
Plot one or more results from running retro_dom_pdfs.py script
"""

from __future__ import absolute_import, division, print_function

__all__ = '''
    ks_test
    plot_run_info
    parse_args
    main
'''.split()

from argparse import ArgumentParser
import cPickle as pickle
from os.path import expanduser, expandvars, isdir, join
from os import makedirs
import sys

import numpy as np
import matplotlib as mpl
mpl.use('agg')
import matplotlib.pyplot as plt


HIT_TIMES = np.linspace(0, 2000, 201)
SAMPLE_HIT_TIMES = 0.5 * (HIT_TIMES[:-1] + HIT_TIMES[1:])


def ks_test(a, b):
    """https://en.wikipedia.org/wiki/Kolmogorov%E2%80%93Smirnov_test"""
    acs = np.cumsum(a)
    macs = np.max(acs)
    if macs == 0:
        return np.nan
    else:
        acs /= np.max(acs)
    bcs = np.cumsum(b)
    mbcs = np.max(bcs)
    if mbcs == 0:
        return np.nan
    else:
        bcs /= np.max(bcs)
    return np.max(np.abs(bcs - acs))


def plot_run_info(
        files, labels, outdir, fwd_hists=None, data_or_sim_label=None,
        paired=False, gradient=False, plot=True
    ):
    """Plot `files` using `labels` (one for each file).

    Parameters
    ----------
    files : string or iterable thereof
    labels : string or iterable thereof
    outdir : string
    fwd_hists : string, optional
    data_or_sim_label : string, optional

    """
    if isinstance(files, basestring):
        files = [files]
    if isinstance(labels, basestring):
        labels = [labels]

    outdir = expanduser(expandvars(outdir))

    if fwd_hists is not None:
        with open(expanduser(expandvars(fwd_hists)), 'rb') as fobj:
            fwd_hists = pickle.load(fobj)
            if 'binning' in fwd_hists:
                t_min = fwd_hists['binning']['t_min']
                t_max = fwd_hists['binning']['t_max']
                num_bins = fwd_hists['binning']['num_bins']
                spacing = fwd_hists['binning']['spacing']
                assert spacing == 'linear', spacing
                fwd_hists_binning = np.linspace(t_min, t_max, num_bins + 1)
            else:
                fwd_hists_binning = HIT_TIMES

            if 'results' in fwd_hists:
                fwd_hists = fwd_hists['results']
            else:
                raise ValueError('Could not find key "results" in fwd hists!')

    if not isdir(outdir):
        makedirs(outdir)

    run_infos = []
    all_string_dom_pairs = set()
    mc_true_params = None
    for filepath in files:
        filepath = expanduser(expandvars(filepath))
        if isdir(filepath):
            filepath = join(filepath, 'run_info.pkl')
        with open(expanduser(expandvars(filepath)), 'rb') as fobj:
            run_info = pickle.load(fobj)
        run_infos.append(run_info)
        all_string_dom_pairs.update(run_info['results'].keys())
        if data_or_sim_label is None:
            data_or_sim_label = (
                'Simulation: '
                + run_info['sim_to_test'].replace('_', ' ').capitalize()
            )

        if mc_true_params is None:
            if 'sim' in run_info:
                mc_true_params = run_info['sim']['mc_true_params']
            else:
                print('mc_true_params not in run_info', filepath)

    params_label = None
    if mc_true_params is not None:
        params_label = []
        for plab, pval in mc_true_params.items():
            units = ''

            if plab == 't':
                pval = format(int(pval), 'd')
                #plab = r'{}'.format(plab)
                units = r'\, \rm{ ns}'

            elif plab in 'x y z'.split():
                pval = format(pval, '0.1f')
                #plab = r'${}$'.format(plab)
                units = r'\, \rm{ m}'

            elif plab in 'track_energy cascade_energy'.split():
                pval = format(int(pval), 'd')
                plab = r'E_{\rm %s}' % plab.split('_')[0]
                units = r'\, \rm{ GeV}'

            elif plab in 'track_azimuth track_zenith cascade_azimuth cascade_zenith'.split():
                pval = format(pval / np.pi, '.2f')
                if 'azimuth' in plab:
                    ltr = r'\phi'
                elif 'zenith' in plab:
                    ltr = r'\theta'
                plab = ltr + r'_{\rm %s}' % plab.split('_')[0]
                units = r'\, \pi'

            params_label.append('{}={}{}'.format(plab, pval, units))
        params_label = '$' + r',\;'.join(params_label) + '$'

    if plot:
        fig, ax = plt.subplots(1, 1, figsize=(10, 8), dpi=72)
    tots_incl_noise = []
    tots_excl_noise = []
    kss = []
    ref_tots_incl_noise = []
    ref_tots_excl_noise = []
    for string, dom in sorted(all_string_dom_pairs):
        if plot:
            ax.clear()
        all_zeros = True
        xmin = np.inf
        xmax = -np.inf
        ref_y = None
        if fwd_hists:
            if (string, dom) in fwd_hists:
                ref_y = fwd_hists[(string, dom)]
                ref_y = np.array([ref_y[0]] + ref_y.tolist())
                nonzero_mask = ref_y != 0 #~np.isclose(ref_y, 0)
                if np.any(nonzero_mask):
                    all_zeros = False
                    #ref_y_all_zeros = False
                    min_mask = (ref_y - ref_y.min()) >= 0.01 * (ref_y.max() - ref_y.min())
                    xmin = min(xmin, fwd_hists_binning[min_mask].min())
                    xmax = max(xmax, fwd_hists_binning[min_mask].max())
            else:
                ref_y = np.zeros_like(fwd_hists_binning)

            valid_ref_y = np.ma.masked_invalid(ref_y)
            ref_tots_incl_noise.append(np.sum(valid_ref_y))
            ref_tots_excl_noise.append(np.sum(valid_ref_y - valid_ref_y.min()))

            if plot:
                ax.step(
                    fwd_hists_binning, ref_y,
                    lw=1,
                    label='Forward sim',
                    clip_on=True,
                    #color='C0'
                )

        colors = ['C%d' % i for i in range(1, 10)]
        linestyles = ['-', '--']
        linewidths = [5, 3, 2, 2, 2, 2, 2]

        for plt_i, (label, run_info) in enumerate(zip(labels, run_infos)):
            if len(tots_incl_noise) <= plt_i:
                tots_incl_noise.append([])
                tots_excl_noise.append([])
                kss.append([])
            results = run_info['results']
            if (string, dom) in results.keys():
                rslt = results[(string, dom)]
                if 'pexp_at_hit_times' in rslt:
                    y = rslt['pexp_at_hit_times']
                else:
                    y = rslt['exp_p_at_hit_times']
                if isinstance(y, int):
                    print(y)
                    print((string, dom))
                    print(label)
                nonzero_mask = y != y[0] #~np.isclose(y, 0)
                if np.any(nonzero_mask):
                    all_zeros = False
                    min_mask = y >= 0.01 * y.max()
                    xmin = min(xmin, SAMPLE_HIT_TIMES[min_mask].min())
                    xmax = max(xmax, SAMPLE_HIT_TIMES[min_mask].max())
            else:
                y = np.zeros_like(SAMPLE_HIT_TIMES)

            masked_y = np.ma.masked_invalid(y)
            tot_excl_noise = (masked_y - masked_y.min()).sum()
            tot_incl_noise = masked_y.sum()
            if tot_excl_noise != 0:
                tots_excl_noise[plt_i].append(tot_excl_noise)
                tots_incl_noise[plt_i].append(tot_incl_noise)
            else:
                tots_excl_noise[plt_i].append(0)
                tots_incl_noise[plt_i].append(0)
            kss[plt_i].append(ks_test(y, ref_y[1:]))

            #kl_div = None
            custom_label = label
            #if ref_y is not None: # and not ref_y_all_zeros:
            #    abs_mean_diff = np.abs(np.mean(y - ref_y[1:]))
            #    #rel_abs_mean_diff = abs_mean_diff / np.sum(ref_y[1:])

            #    mask = ref_y[1:] > 0
            #    kl_ref_vals = ref_y[1:][mask]
            #    kl_ref_vals /= np.sum(kl_ref_vals)

            #    y_prob_vals = y[mask]
            #    y_prob_vals /= np.sum(y_prob_vals)

            #    with np.errstate(divide='ignore'):
            #        kl_div = -np.sum(kl_ref_vals * np.log(y_prob_vals / kl_ref_vals))
            #    custom_label = format(rel_abs_mean_diff, '9.6f') + '  ' + label

            if paired:
                c_idx, ls_idx = divmod(plt_i, 2)
                color = colors[c_idx]
                linestyle = linestyles[ls_idx]
            else:
                color = None
                linestyle = None

            if plot:
                ax.plot(
                    SAMPLE_HIT_TIMES, y,
                    label=custom_label,
                    color=color,
                    linestyle=linestyle,
                    linewidth=linewidths[plt_i],
                    clip_on=True
                )

        if all_zeros:
            continue

        if xmin == xmax:
            xmin = 0
            xmax = 2000

        if plot:
            ax.set_xlim(xmin, xmax)
            ax.set_ylim(0, ax.get_ylim()[1])

            for pos in 'bottom left top right'.split():
                ax.spines[pos].set_visible(False)

            ax.xaxis.set_ticks_position('none')
            ax.yaxis.set_ticks_position('none')

            ax.xaxis.tick_bottom()
            ax.yaxis.tick_left()

            #if kl_div is not None:
            #title = ' '*6 + 'Abs diff'.ljust(8) + '  ' + 'Simulation'
            #else:
            title = 'Code'

            leg = ax.legend(
                title=title,
                #loc='best',
                loc='upper right',
                #frameon=False,
                framealpha=0.7,
                prop=dict(family='monospace', size=12)
            )
            plt.setp(leg.get_title(), family='monospace', fontsize=12)
            #if kl_div is not None:
            #leg._legend_box.align = "left"
            leg.get_frame().set_linewidth(0)
            ax.set_xlabel('Time from event vertex (ns)', fontsize=14)

            if data_or_sim_label is not None:
                plt.text(
                    0.5, 1.1,
                    data_or_sim_label,
                    ha='center', va='bottom',
                    transform=ax.transAxes,
                    fontsize=16
                )
            if params_label is not None:
                plt.text(
                    0.5, 1.05,
                    params_label,
                    ha='center', va='bottom',
                    transform=ax.transAxes,
                    fontsize=12
                )

            ax.text(
                0.5, 1.0,
                'String {}, DOM {}'.format(string, dom),
                ha='center', va='bottom',
                transform=ax.transAxes,
                fontsize=14
            )

            fbasename = 'string_{}_dom_{}'.format(string, dom)
            fig.savefig(join(outdir, fbasename + '.png'))
            sys.stdout.write('({}, {}) '.format(string, dom))
            sys.stdout.flush()
    sys.stdout.write('\n\n')
    sys.stdout.flush()

    ref_tots_incl_noise = np.array(ref_tots_incl_noise)
    ref_tots_excl_noise = np.array(ref_tots_excl_noise)
    ref_tot_incl_noise = np.sum(ref_tots_incl_noise)
    ref_tot_excl_noise = np.sum(ref_tots_excl_noise)
    print(
        '{:9s}  {:16s}  {:16s}  {}'
        .format(
            'KS'.ljust(7),
            'Ratio incl noise'.ljust(16),
            'Ratio excl noise'.ljust(16),
            'Label'
        )
    )
    for label, ks, tot_incl_noise, tot_excl_noise in zip(labels,
                                                         kss,
                                                         tots_incl_noise,
                                                         tots_excl_noise):
        ks = np.array(ks)
        mask = ~np.isnan(ks)
        ks_wtd_avg = (
            np.sum(ks[mask] * ref_tots_excl_noise[mask])
            / np.sum(ref_tots_excl_noise[mask])
        )
        print(
            '{:9s}  {:16s}  {:16s}  {}'
            .format(
                format(ks_wtd_avg, '.7f').rjust(9),
                format(np.sum(tot_incl_noise) / ref_tot_incl_noise, '.7f').rjust(16),
                format(np.sum(tot_excl_noise) / ref_tot_excl_noise, '.7f').rjust(16),
                label
            )
        )


def parse_args(description=__doc__):
    """Parse command line arguments"""
    parser = ArgumentParser(description=description)
    parser.add_argument(
        '--files', nargs='+', required=True,
        help='''One or more *run_info.pkl files to plot'''
    )
    parser.add_argument(
        '--labels', nargs='+', required=True,
        help='''One (legend) label per file'''
    )
    parser.add_argument(
        '--fwd-hists', required=False,
        help='''Path to the forward-simulation pickle file'''
    )
    parser.add_argument(
        '--outdir', required=True,
        help='''Directory into which to place the plots.'''
    )
    parser.add_argument(
        '--paired', action='store_true',
        help='''Display style for visually grouping pairs of lines with
        same-colors but different line styles.'''
    )
    parser.add_argument(
        '--gradient', action='store_true',
        help='''Display style for visually showing a progression from line to
        line via a color gradient.'''
    )
    parser.add_argument(
        '--no-plot', action='store_true',
        help='''Do _not_ make plots, just print summary statistics.'''
    )
    return parser.parse_args()


def main():
    """Get command line args, translate, and run plot function"""
    kwargs = vars(parse_args())
    kwargs['plot'] = not kwargs.pop('no_plot')
    plot_run_info(**kwargs)


if __name__ == '__main__':
    main()
