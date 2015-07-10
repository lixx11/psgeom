#!/usr/bin/env python

import numpy as np
import os
import unittest
import h5py

from psgeom import moveable
from psgeom import sensors
from psgeom import translate
from psgeom import detector
from psgeom.translate import _cheetah_to_twobyones

PIXEL_TOLERANCE_um = 10.0



# ---- moveable.py -------------------------------------------------------------

def test_translation_matrix_from_vector():
    
    x = np.random.randint(0,5,size=(3))    
    y = np.random.randint(0,5,size=(3))
    
    yp = np.ones(4)
    yp[:3] = y
    
    T = moveable._translation_matrix_from_vector(x)
    
    assert np.all(np.dot(T, yp)[:3] == x + y)
    assert np.dot(T, yp)[3] == 1.0
    
    
def test_rotation_matrix_from_angles():
    
    x = np.array([1.0, 0.0, 0.0]) # vector pointing at x
    
    Rz = moveable._rotation_matrix_from_angles(90.0, 0.0, 0.0)
    y = np.dot(Rz, x)
    np.testing.assert_array_almost_equal(y, np.array([0.0, 1.0, 0.0]),
                                         err_msg='Rz err')
    
    Rx = moveable._rotation_matrix_from_angles(0.0, 0.0, 90.0)
    z = np.dot(Rx, y)
    np.testing.assert_array_almost_equal(z, np.array([0.0, 0.0, 1.0]),
                                         err_msg='Rx err')
    
    Ry = moveable._rotation_matrix_from_angles(0.0, -90.0, 0.0)
    x = np.dot(Ry, z)
    np.testing.assert_array_almost_equal(x, x, err_msg='Ry err')
    

def test_angle_retrieval():

    for i in range(100):

        alpha = np.random.rand() * 180.0
        beta  = np.random.rand() * 180.0
        gamma = np.random.rand() * 180.0

        R = moveable._rotation_matrix_from_angles(gamma, beta, alpha)

        I = np.eye(3)
        Ip = np.dot(R, I)

        gp, bp, ap = moveable._angles_from_rotated_frame(Ip[:,0], Ip[:,1], Ip[:,2])

        #print np.array([gamma, beta, alpha]), np.array([gp, bp, ap])

        # test to make sure they rotate to the same thing
        R2 = moveable._rotation_matrix_from_angles(gp, bp, ap)

        assert np.sum( np.abs( R - R2 ) ) < 1e-12


# ---- sensors.py --------------------------------------------------------------

class TestPixelArraySensor(object):
    
    def setup(self):
        
        self.shape = (185, 388)
        self.pixel_shape = (1.0, 1.0)
        
        self.rotation_angles = np.random.rand(3) * 360.0
        self.translation     = np.random.randn(3)
        
        self.PAS = sensors.PixelArraySensor(self.shape, self.pixel_shape, 
                                            type_name='Test', id_num=0, parent=None,
                                            rotation_angles=self.rotation_angles, 
                                            translation=self.translation)
    
    
    def test_local_transform(self):
        R = moveable._rotation_matrix_from_angles(*self.rotation_angles, 
                                         dummy_dimension=True)
        T = moveable._translation_matrix_from_vector(self.translation)
        L_ref = np.dot(T, R)
        L_ans = self.PAS.local_transform
        np.testing.assert_array_almost_equal(L_ref, L_ans)
    
    
    def test_global_transform(self):
        
        ra_p = np.random.rand(3) * 360.0
        t_p  = np.random.randn(3)
        
        Rp = moveable._rotation_matrix_from_angles(*ra_p, dummy_dimension=True)
        Tp = moveable._translation_matrix_from_vector(t_p)
        
        parent_obj = detector.CompoundDetector(type_name='daddy', 
                                               id_num=0, parent=None,
                                               rotation_angles=ra_p, 
                                               translation=t_p)
                                      
        self.PAS.set_parent(parent_obj)
        
        R = moveable._rotation_matrix_from_angles(*self.rotation_angles, 
                                         dummy_dimension=True)
        T = moveable._translation_matrix_from_vector(self.translation)
        
        G_ref = np.dot( np.dot( np.dot(Tp, Rp), T), R) # T_1 . R_1 . T_2 . R_2
        G_ans = self.PAS.global_transform
        
        np.testing.assert_array_almost_equal(G_ref, G_ans)
    
    
    def test_evaluate_transform(self):
    
        # for rotation
        x = np.array([[1.0, 0.0, 0.0]]) # vector pointing at x
        Rz = moveable._rotation_matrix_from_angles(90.0, 0.0, 0.0, 
                                                   dummy_dimension=True)                                         
        ref = np.array([[0.0, 1.0, 0.0]])
        ans = detector.CompoundDetector._evaluate_transform(Rz, x)
        np.testing.assert_array_almost_equal(ans, ref, err_msg='rotation')
                                         
        # for translation
        x = np.random.randint(0,5,size=(1,3))    
        y = np.random.randint(0,5,size=(1,3))    
        T = moveable._translation_matrix_from_vector(x)    
        assert np.all( detector.CompoundDetector._evaluate_transform(T, y) == x + y )
    
    
    def test_untransformed_xyz(self):
        uxyz = self.PAS.untransformed_xyz
        assert uxyz.shape[:-1] == self.shape
        # remember, slow is y convention...
        assert np.max(uxyz[...,0]) == (self.shape[1]-1) * self.pixel_shape[1]
        assert np.max(uxyz[...,1]) == (self.shape[0]-1) * self.pixel_shape[0]
        
    
    def test_xyz(self):
        
        uxyz = self.PAS.untransformed_xyz
        
        buff = np.ones( list(uxyz.shape[:-1]) + [1], dtype=uxyz.dtype)
        uxyzd = np.concatenate([uxyz, buff], axis=-1)
        
        R = moveable._rotation_matrix_from_angles(*self.rotation_angles, 
                                                  dummy_dimension=True)
        T = moveable._translation_matrix_from_vector(self.translation)
        
        xyz_ans = np.dot(uxyzd, np.dot(T, R).T)
        np.testing.assert_array_almost_equal(self.PAS.xyz, xyz_ans[...,:3])
    


# ---- detector.py -------------------------------------------------------------

class TestCompoundDetector(object):
    
    def setup(self):
        self.geom = detector.CompoundDetector.from_psana_file('ref_files/refgeom_psana.data')
        
    
    def test_read_write(self):

        self.geom.to_psana_file('test.data')
        geom2 = detector.CompoundDetector.from_psana_file('test.data')
        
        assert self.geom.xyz.shape == geom2.xyz.shape, 'shape/element mismatch'            
        np.testing.assert_allclose(self.geom.xyz, geom2.xyz, rtol=1e-3)

        os.remove('test.data')
    
    def test_xyz_vs_old_implementation(self):
    
        # ---- get the geometry Mikhail-style
        try:
            from PSCalib.GeometryAccess import GeometryAccess
            ga = GeometryAccess('refgeom_psana.data')
            xyz_old = ga.get_pixel_coords()
                
        except:
            # if that don't work, load a pre-saved answer
            print 'could not use GeometryAccess, loading saved xyz'
            xyz_old = np.load('ref_files/GA_saved_1-end.npy')
        
        # some np-foo to move the 3-d x,y,z axis from first dim to last
        xyz_old = np.rollaxis(np.array(xyz_old), 0, 7) # send 0 --> 7
        xyz_old = np.squeeze(xyz_old)
    
        geom = detector.CompoundDetector.from_psana_file('ref_files/refgeom_psana.data')
        xyz_new = np.squeeze(geom.xyz)
    
        assert xyz_new.shape == xyz_old.shape, 'shape mismatch'
    
        err = np.sum( np.abs(xyz_new - xyz_old) ) / float(np.product(xyz_new.shape))
        print 'Mean Absolute Error: %f um / px' % err
        num_more_than_1px_err = np.sum( np.abs(xyz_new - xyz_old) > 109.92 )
    
        assert err < 10.0, 'error greater than 10um avg per px (%f)' % err
        assert num_more_than_1px_err < 7500, '>7500 pix w err > 1 px'
    
        #np.testing.assert_allclose(xyz_new, xyz_old, atol=2 * 110.0)
        
        
    def test_leaves(self):
        assert len(self.geom.leaves) == 32, 'got: %d' % len(self.geom.leaves)
        
    
    
class TestCspad(object):
    
    def setup(self):
        self.cspad = detector.Cspad.from_psana_file('ref_files/refgeom_psana.data')
        
    def test_basisgrid_roundtrip(self):
        bg = self.cspad.to_basisgrid()
        cspad2 = detector.Cspad.from_basisgrid(bg)
        
        assert self.cspad.num_pixels == cspad2.num_pixels
        np.testing.assert_allclose( np.squeeze(self.cspad.xyz), 
                                    np.squeeze(cspad2.xyz),
                                    atol=PIXEL_TOLERANCE_um )
    
    

# ---- translate.py ------------------------------------------------------------
    
class TestTranslate(object):
    """
    Will test read/write from external software packages
    """
    
    def setup(self):
        self.cd = detector.CompoundDetector.from_psana_file('ref_files/refgeom_psana.data')
        self.cspad = detector.Cspad.from_psana_file('ref_files/refgeom_psana.data')
        
        
    def test_asic_basis_grid(self):
        # this is the method to_basisgrid implemented by the class Cspad
        asic_bg = self.cspad.to_basisgrid()
        
        xyz = asic_bg.to_explicit().reshape(4,16,185,194,3)
        print xyz.shape
        
        # VISUALLY CONFIRMED AS VERY CLOSE -- TJL June 17 2015
        # still need real test
        
        # import matplotlib.pyplot as plt
        # from psgeom import draw
        # 
        # fig = plt.figure()
        # ax = plt.subplot(111)
        # draw.sketch_2x1s(xyz[:,::2,:,:], ax)
        # draw.sketch_2x1s(xyz[:,1::2,:,:], ax)
        # plt.show()
        
        
    def test_to_basis_grid(self):
        
        bg = self.cd.to_basisgrid()
        assert bg.num_grids == len(self.cd.leaves)
        
        xyz = np.squeeze(self.cd.xyz)
        
        for i in range(4):
            for j in range(8):
                
                # only test first ASIC to avoid middle-row complications
                bg_xyz_ij = bg.grid_as_explicit(i*8 + j)[:,:193,:]
                cd_xyz_ij = xyz[i,j,:,:193,:]
                print i, j, np.sum( np.abs(bg_xyz_ij - cd_xyz_ij))
                np.testing.assert_allclose(bg_xyz_ij, cd_xyz_ij, 
                                           atol=PIXEL_TOLERANCE_um)
    
        
        
    def from_basis_grid(self):
        
        bg = self.cd.to_basisgrid()
        new = detector.CompoundDetector.from_basisgrid(bg)
        
        cd_xyz  = self.cd.xyz
        new_xyz = new.xyz
                
        for i in range(4):
            for j in range(8):
                np.testing.assert_allclose(cd_xyz[0,i,j,:,:193], 
                                           new_xyz[i*8 + j,:,:193],
                                           rtol=1e-6, atol=PIXEL_TOLERANCE_um)
        
        
        
    def test_psf_text(self):
        
        raise unittest.SkipTest
        
        self.cd.to_text_file('ref_files/cd_psf.txt')
        self.cspad.to_text_file('ref_files/cspad_psf.txt')
        
        # todo : load & ensure consistent
        cd2 = detector.CompoundDetector.from_text_file('ref_files/cd_psf.txt')
        cspad2 = detector.CompoundDetector.from_text_file('ref_files/cd_psf.txt')
        
        np.testing.assert_allclose(self.cd.xyz, cd2.xyz)
        np.testing.assert_allclose(self.cspad.xyz, cspad2.xyz)
        
        os.remove('ref_files/cd_psf.txt')
        os.remove('ref_files/cspad_psf.txt')
    
        
    def test_cheetah_roundtrip(self):
        
        self.cspad.to_cheetah_file('ref_files/tmp_cheetah_geom.h5')
        cspad2 = detector.Cspad.from_cheetah_file('ref_files/tmp_cheetah_geom.h5')
                
        np.testing.assert_allclose( np.squeeze(self.cspad.xyz),
                                    np.squeeze(cspad2.xyz),
                                    err_msg='round trip fail',
                                    atol=PIXEL_TOLERANCE_um)
        os.remove('ref_files/tmp_cheetah_geom.h5')
        
        
    def test_cheetah_values(self):
        
        # the cheetah pixels are just the xyz, so we can load them and use them
        # to compare to our implementation
        
        f = h5py.File('ref_files/refgeom_cheetah.h5', 'r')
        
        x = -1.0 * _cheetah_to_twobyones( np.array(f['x']) * 1000000.0 )
        y = _cheetah_to_twobyones( np.array(f['y']) * 1000000.0 )
        z = _cheetah_to_twobyones( np.array(f['z']) )
        
        f.close()
        
        ref_xyz = np.rollaxis( np.array([x,y,z]), 0, 4) # to shape (32,...,3)
        tst = detector.Cspad.from_cheetah_file('ref_files/refgeom_cheetah.h5')
        tst_xyz = tst.xyz.reshape(32,185,388,3)
                
        np.testing.assert_allclose(tst_xyz[:,0,0,:],
                                   ref_xyz[:,0,0,:],
                                   atol=PIXEL_TOLERANCE_um,
                                   err_msg='panel 1st pixels off')
        
        
                                   
        # cheetah does not deal correctly with the large center pixels, so
        # we test around that
        assert np.max( np.abs(tst_xyz - ref_xyz) ) < 500.0
        np.testing.assert_allclose(tst_xyz[:,:,:193,:], ref_xyz[:,:,:193,:],
                                   atol=PIXEL_TOLERANCE_um,
                                   err_msg='panels off in general')
        
        
    def test_cheetah_crystfel_consistency(self):
        
        # the following two files were generated using the "make_pixelmap"
        # program by TAW, the cheetah file being generated from the CrystFEL
        # conversion done by TJL 7/8/15
        
        #raise unittest.SkipTest
        
        # very close but ~1/2 pixel off. Does cheetah plot pixel corners or
        # centers? -- TJL 7/8/15
        
        cheetah  = detector.Cspad.from_cheetah_file('ref_files/refgeom_cheetah.h5')
        crystfel = detector.Cspad.from_crystfel_file('ref_files/refgeom_crystfel.geom')
        
        np.testing.assert_allclose(np.squeeze(cheetah.xyz),
                                   np.squeeze(crystfel.xyz),
                                   atol=PIXEL_TOLERANCE_um)
       
        
    def test_crystfel_roundtrip(self):
        
        self.cspad.to_crystfel_file('ref_files/tmp_crystfel.geom')
        
        # Note by TJL, 7/8/15
        # there is a round-trip error of less than 1 micron per pixel
        # I believe this is due to the fact that CrystFEL assumes sensors
        # are orthogonal to the beam (no z-info), but that remains to be
        # verified
        
        cd2 = detector.Cspad.from_crystfel_file('ref_files/tmp_crystfel.geom')
        
        
        # be sure error is less than 1 micron in x/y, 0.2 mm in z
        assert np.max(np.abs( np.squeeze(self.cspad.xyz[...,:2]) - np.squeeze(cd2.xyz[...,:2]) )) < 1.0
        assert np.max(np.abs( np.squeeze(self.cspad.xyz) - np.squeeze(cd2.xyz) )) < 200.0
        
        np.testing.assert_allclose(np.squeeze(self.cd.xyz),
                                   np.squeeze(cd2.xyz),
                                   err_msg='round trip fail',
                                   atol=PIXEL_TOLERANCE_um,
                                   rtol=1e-3)
                                           
        os.remove('ref_files/tmp_crystfel.geom')

    
    
    
if __name__ == '__main__':
    #test_create_cspad()
    test_xyz_vs_old_implementation()
    
    
    