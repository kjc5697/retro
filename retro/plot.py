#!/usr/bin/env python

from power_axis import PowerAxis
from hypo_vector import segment_hypo
from hypo_fast import hypo
import numpy as np
import math

if __name__ == '__main__':

    # for plotting
    import matplotlib as mpl
    mpl.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from mpl_toolkits.mplot3d import Axes3D
    import time
    # plot setup
    fig = plt.figure(figsize=(10,10))
    ax = fig.add_subplot(221,projection='3d')
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('z')
    ax2 = fig.add_subplot(222)
    ax3 = fig.add_subplot(223)
    ax4 = fig.add_subplot(224)

    plt_lim = 50

    ax.set_xlim((-plt_lim,plt_lim))
    ax.set_ylim((-plt_lim,plt_lim))
    ax.set_zlim((-plt_lim,plt_lim))
    ax.grid(True)


    # same as CLsim
    t_bin_edges = np.linspace(0, 500, 51)
    r_bin_edges = PowerAxis(0, 200, 20, 2)
    theta_bin_edges = np.arccos(np.linspace(-1, 1, 51))[::-1]
    phi_bin_edges = np.linspace(0, 2*np.pi, 37)

    my_hypo = hypo(65., 1., 10., -50., theta=1.08, phi=0.96, trck_energy=20., cscd_energy=25.)
    my_hypo.set_binning(t_bin_edges, r_bin_edges, theta_bin_edges, phi_bin_edges)

    # kevin array
    t0 = time.time()
    kevin_hypo = segment_hypo(65., 1., 10., -50, 1.08, 0.96, 20., 25.)
    kevin_hypo.set_binning(50., 20., 50., 36., 500., 200.)
    kevin_hypo.set_dom_location(50., 0., 10., 0.)
    kevin_hypo.vector_photon_matrix()
    print 'took %.2f ms to calculate z_matrix'%((time.time() - t0)*1000)
    z_indices = kevin_hypo.indices_array
    z_values = kevin_hypo.values_array
    z_matrix = np.zeros((len(t_bin_edges) - 1, len(r_bin_edges) - 1, len(theta_bin_edges) - 1, len(phi_bin_edges) - 1))

    #debug prints
    #print kevin_hypo.variables_array.shape
    #print kevin_hypo.variables_array[6, :]
    #print kevin_hypo.indices_array[3, :]
    #print kevin_hypo.values_array[2, :]
   
    for col in xrange(kevin_hypo.number_of_increments):
        idx = (int(z_indices[0, col]), int(z_indices[1, col]), int(z_indices[2, col]), int(z_indices[3, col]))
        if z_indices[1, col] < kevin_hypo.r_max:
            z_matrix[idx] += z_values[0, col]
    print 'total number of photons in kevin matrix = %i (%.2f %%)'%(z_matrix.sum(), z_matrix.sum()/my_hypo.tot_photons*100.)

    # plot the track as a line
    x_0, y_0, z_0 = my_hypo.track.point(my_hypo.track.t0)
    #print 'track vertex', x_0, y_0, z_0
    x_e, y_e, z_e  = my_hypo.track.point(my_hypo.track.t0 + my_hypo.track.dt)
    ax.plot([x_0,x_e],[y_0,y_e],zs=[z_0,z_e])
    ax.plot([-plt_lim,-plt_lim],[y_0,y_e],zs=[z_0,z_e],alpha=0.3,c='k')
    ax.plot([x_0,x_e],[plt_lim,plt_lim],zs=[z_0,z_e],alpha=0.3,c='k')
    ax.plot([x_0,x_e],[y_0,y_e],zs=[-plt_lim,-plt_lim],alpha=0.3,c='k')
    
    t0 = time.time()
    hits, n_t, n_p, n_l = my_hypo.get_matrices(50., 0., 10., 0.)
    print 'took %.2f ms to calculate z'%((time.time() - t0)*1000)
    z = np.zeros((len(t_bin_edges) - 1, len(r_bin_edges) - 1, len(theta_bin_edges) - 1, len(phi_bin_edges) - 1))
    for hit in hits:
        #print hit
        idx, count = hit
        z[idx] = count
    print 'total number of photons in matrix = %i (%.2f %%)'%(z.sum(), z.sum()/my_hypo.tot_photons*100.)

    print 'total_residual = ',(z - z_matrix).sum()/z.sum()

    #create differential matrix
    z_diff = z_matrix - z

    #create percent differnt matrix
    z_per = np.zeros_like(z_matrix)
    mask = z != 0
    z_per[mask] = z_matrix[mask] / z[mask] -1

    #cmap = 'gnuplot_r'
    cmap = mpl.cm.get_cmap('bwr')
    cmap.set_under('w')
    cmap.set_bad('w')

    #make first plot
    tt, yy = np.meshgrid(t_bin_edges, r_bin_edges)
    zz = z_diff.sum(axis=(2,3))
    z_vmax = np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax2.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax2.set_xlabel('t')
    ax2.set_ylabel('r')
    cb2 = plt.colorbar(mg, ax=ax2)

    tt, yy = np.meshgrid(t_bin_edges, theta_bin_edges)
    zz = z_diff.sum(axis=(1,3))
    z_vmax = np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax3.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax3.set_xlabel('t')
    ax3.set_ylabel(r'$\theta$')
    ax3.set_ylim((0,np.pi))
    cb3 = plt.colorbar(mg, ax=ax3)

    tt, yy = np.meshgrid(t_bin_edges, phi_bin_edges)
    zz = z_diff.sum(axis=(1,2))
    z_vmax = np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax4.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax4.set_xlabel('t')
    ax4.set_ylabel(r'$\phi$')
    ax4.set_ylim((0,2*np.pi))
    cb4 = plt.colorbar(mg, ax=ax4)
    
    ax2.grid(True, 'both', color='g')
    ax3.grid(True, 'both', color='g')
    ax4.grid(True, 'both', color='g')

    plt.show()
    plt.savefig('hypo_diff11.png',dpi=300)

    #clear colorbars
    cb2.remove()
    cb3.remove()
    cb4.remove()
    
    #make second plot
    tt, yy = np.meshgrid(t_bin_edges, r_bin_edges)
    zz = z_per.sum(axis=(2,3))
    z_vmax = 5#np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax2.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax2.set_xlabel('t')
    ax2.set_ylabel('r')
    cb2 = plt.colorbar(mg, ax=ax2)

    tt, yy = np.meshgrid(t_bin_edges, theta_bin_edges)
    zz = z_per.sum(axis=(1,3))
    z_vmax = 5#np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax3.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax3.set_xlabel('t')
    ax3.set_ylabel(r'$\theta$')
    ax3.set_ylim((0,np.pi))
    cb3 = plt.colorbar(mg, ax=ax3)

    tt, yy = np.meshgrid(t_bin_edges, phi_bin_edges)
    zz = z_per.sum(axis=(1,2))
    z_vmax = 5#np.maximum(np.abs(np.min(zz)), np.max(zz))
    mg = ax4.pcolormesh(tt, yy, zz.T, vmin=-z_vmax, vmax=z_vmax, cmap=cmap)
    ax4.set_xlabel('t')
    ax4.set_ylabel(r'$\phi$')
    ax4.set_ylim((0,2*np.pi))
    cb4 = plt.colorbar(mg, ax=ax4)
    
    ax2.grid(True, 'both', color='g')
    ax3.grid(True, 'both', color='g')
    ax4.grid(True, 'both', color='g')
    
    plt.show()
    plt.savefig('hypo_per11.png',dpi=300)

    #clear colorbars
    cb2.remove()
    cb3.remove()
    cb4.remove()

    #change colorbar for non diverging data
    #cmap = 'gnuplot_r'
    cmap = mpl.cm.get_cmap('Blues')
    cmap.set_under('w')
    cmap.set_bad('w')
    
    #make third plot
    tt, yy = np.meshgrid(t_bin_edges, r_bin_edges)
    zz = z_matrix.sum(axis=(2,3))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax2.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax2.set_xlabel('t')
    ax2.set_ylabel('r')
    cb2 = plt.colorbar(mg, ax=ax2)

    tt, yy = np.meshgrid(t_bin_edges, theta_bin_edges)
    zz = z_matrix.sum(axis=(1,3))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax3.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax3.set_xlabel('t')
    ax3.set_ylabel(r'$\theta$')
    ax3.set_ylim((0,np.pi))
    cb3 = plt.colorbar(mg, ax=ax3)

    tt, yy = np.meshgrid(t_bin_edges, phi_bin_edges)
    zz = z_matrix.sum(axis=(1,2))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax4.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax4.set_xlabel('t')
    ax4.set_ylabel(r'$\phi$')
    ax4.set_ylim((0,2*np.pi))
    cb4 = plt.colorbar(mg, ax=ax4)
    
    ax2.grid(True, 'both', color='g')
    ax3.grid(True, 'both', color='g')
    ax4.grid(True, 'both', color='g')
    
    plt.show()
    plt.savefig('hypo_kevin11.png',dpi=300)

    #clear colorbars
    cb2.remove()
    cb3.remove()
    cb4.remove()
    
    #make fourth plot
    tt, yy = np.meshgrid(t_bin_edges, r_bin_edges)
    zz = z.sum(axis=(2,3))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax2.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax2.set_xlabel('t')
    ax2.set_ylabel('r')
    cb2 = plt.colorbar(mg, ax=ax2)

    tt, yy = np.meshgrid(t_bin_edges, theta_bin_edges)
    zz = z.sum(axis=(1,3))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax3.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax3.set_xlabel('t')
    ax3.set_ylabel(r'$\theta$')
    ax3.set_ylim((0,np.pi))
    cb3 = plt.colorbar(mg, ax=ax3)

    tt, yy = np.meshgrid(t_bin_edges, phi_bin_edges)
    zz = z.sum(axis=(1,2))
    z_vmax = np.partition(zz.flatten(), -2)[-2]
    mg = ax4.pcolormesh(tt, yy, zz.T, vmax=z_vmax, cmap=cmap)
    ax4.set_xlabel('t')
    ax4.set_ylabel(r'$\phi$')
    ax4.set_ylim((0,2*np.pi))
    cb4 = plt.colorbar(mg, ax=ax4)
    
    ax2.grid(True, 'both', color='g')
    ax3.grid(True, 'both', color='g')
    ax4.grid(True, 'both', color='g')
 
    plt.show()
    plt.savefig('hypo_philipp11.png',dpi=300)

    #clear colorbars
    cb2.remove()
    cb3.remove()
    cb4.remove()