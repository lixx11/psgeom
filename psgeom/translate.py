

"""
io.py
"""

import os
import getpass
import datetime
import h5py
import math

import numpy as np

from psgeom import sensors
from psgeom import basisgrid


def _check_obj(obj):
    """
    check that the object the a detector geometry is being loaded into is "valid"
    """
    # NOT IMPLEMENTED
    return



# ---- psana -------------------------------------------------------------------

def load_psana(obj, filename):
    """
    """
    
    _check_obj(obj)

    print 'Loading: %s' % filename

    # ---- load information into 2 tables: id_info (names) & trt (data)

    # types/names and id numbers -- unique name is 2 fields
    id_info = np.genfromtxt(filename, dtype=None, usecols=(0,1,2,3), autostrip=True)

    # translation & rotation table (trt)
    trt = np.genfromtxt(filename, dtype=np.float64, usecols=range(4,13), autostrip=True)
    assert trt.shape[1] == 9
    translations = trt[:,0:3]
    rotations    = trt[:,3:6] + trt[:,6:9] # just combine rotations & tilts

    n_rows = len(id_info)
    assert trt.shape[0] == n_rows, 'name/data rows dont match (%d/%d)' % \
                                                    (trt.shape[0], n_rows)


    # ---- find the root of the tree, not to be guarenteed first line
    possible_root_rows = range(n_rows) # elimination

    for i in range(n_rows):
        for j in range(n_rows):
        
            # check to see if row i is listed as a child anywhere
            if (id_info[i][0], id_info[i][1]) == (id_info[j][2], id_info[j][3]):
            
                # if so, we know row i is not a root
                #print "%d is child in row %d" % (i,j)
                if i in possible_root_rows:
                    possible_root_rows.remove(i)
            
        
    # check to make sure we have only a single root
    if len(possible_root_rows) != 1:
        raise IOError('Ambiguous tree structure in geometry file. '
                      '%d roots found.' % len(possible_root_rows))
    else:
        root_index = possible_root_rows[0]
        if id_info[root_index][0] != 'IP':
            warnings.warn('Root object is not labeled "IP".')
    

    # ---- traverse tree, adding children / depth frist

    def add_to_tree(current_node_index, parent=None):
    
        cni = current_node_index # shorthand
        cid = (id_info[cni][2], id_info[cni][3])
    
        child_indices = []
        for i in range(n_rows):
            if (id_info[i][0], id_info[i][1]) == cid:
                child_indices.append(i)
        #print '%d --> %s' % (cni, child_indices)
        

        # > if no children, is a SensorElement
    
        if len(child_indices) == 0:
        
            # loop up what type of sensor element we have
            try:
                typ = sensors.type_map[id_info[cni][2]]
            except KeyError:
                raise KeyError('Sensor type: %s not understood.' % id_info[i][2])
            
            
            # TJL note to self:
            # this next line could be problematic if we don't restrict
            # the __init__ method of SensorElements.....
        
            curr = typ(type_name=id_info[cni][2],
                       id_num=id_info[cni][3],
                       parent=parent,
                       rotation_angles=rotations[cni], 
                       translation=translations[cni])
        
        # > else, is a CompoundDetector
        else:
            curr = obj(type_name=id_info[cni][2],
                       id_num=id_info[cni][3],
                       parent=parent,
                       rotation_angles=rotations[cni], 
                       translation=translations[cni])
                   
            for c in child_indices:
                _ = add_to_tree(c, parent=curr)
            
        # we discard all intermediate results, only root is left
        return curr
            
    root_object = add_to_tree(root_index, parent=None)

    return root_object
    
    
def write_psana(detector, filename, title='geometry'):
    """
    write me
    """
    
    f = open(filename, 'w')
    
    # write a header
    author = getpass.getuser()
    today = datetime.date.today()
    date = '%d-%d-%d' % (today.month, today.day, today.year)
    time = datetime.datetime.now().time().isoformat()

    header = """
# TITLE       %s
# AUTHOR      %s
# CALIB_TYPE  geometry
# COMMENT:01  WRITTEN BY USER 
# DATE_TIME   %s\t%s
# PARAM:01    PARENT     - name and version of the parent object
# PARAM:02    PARENT_IND - index of the parent object
# PARAM:03    OBJECT     - name and version of the object
# PARAM:04    OBJECT_IND - index of the new object
# PARAM:05    X0         - x-coordinate [um] of the object origin in the parent frame
# PARAM:06    Y0         - y-coordinate [um] of the object origin in the parent frame
# PARAM:07    Z0         - z-coordinate [um] of the object origin in the parent frame
# PARAM:08    ROT_Z      - object design rotation angle [deg] around Z axis of the parent frame
# PARAM:09    ROT_Y      - object design rotation angle [deg] around Y axis of the parent frame
# PARAM:10    ROT_X      - object design rotation angle [deg] around X axis of the parent frame
# PARAM:11    TILT_Z     - object tilt angle [deg] around Z axis of the parent frame
# PARAM:12    TILT_Y     - object tilt angle [deg] around Y axis of the parent frame
# PARAM:13    TILT_X     - object tilt angle [deg] around X axis of the parent frame
# HDR         PARENT IND        OBJECT IND     X0[um]   Y0[um]   Z0[um]   ROT-Z ROT-Y ROT-X     TILT-Z   TILT-Y   TILT-X
    """ % (title, author, date, time)

    f.write(header)


    fmt_line = '%12s   %d     %12s    %d' + ' %12.6f'*9 + '\n'

    # write a line for the root node
    root_data = ['IP', 0, detector.type_name, detector.id] + [0.0]*9
    root_line = fmt_line % tuple(root_data)
    f.write(root_line)

    # write a line for each child node in the CompoundDetector tree
    def write_children(node):
    
        if hasattr(node, 'children'):
    
            for child in node.children:
                child_data = [node.type_name,
                              node.id,
                              child.type_name,
                              child.id]
                child_data += list(child.translation)
                child_data += list(child.rotation_angles)
                child_data += [0.0]*3
        
                assert len(child_data) == 13
            
                line = fmt_line % tuple(child_data)
                f.write(line)
        
                write_children(child)

    write_children(detector)

    f.close()
    
    return
    

# ---- cheetah -----------------------------------------------------------------
    
def load_cheetah(obj, filename):
    """
    docstring
    """
    
    _check_obj(obj)

    f = h5py.File(filename, 'r')

    if not f.keys() == ['x', 'y', 'z']:
        raise IOError('File: %s is not a valid pixel map, should contain fields'
                      ' ["x", "y", "z"] exlusively' % filename)

    # convert m --> mm
    x = read.enforce_raw_img_shape( np.array(f['x']) * 1000.0 )
    y = read.enforce_raw_img_shape( np.array(f['y']) * 1000.0 )

    # for some reason z is in microns, so um --> mm
    z = read.enforce_raw_img_shape( np.array(f['z']) / 1000.0 )

    f.close()

    bg = BasisGrid()
    shape = (185, 194) # will always be this for each ASIC

    # loop over each ASIC, and convert it into a basis grid
    for i in range(4):
        for j in range(16):

            # extract all the corner positions (code ineligant but explicit)
            # corners are numbered 0 -> 4, starting top left and continuing cw
            corners = np.zeros(( 4, 3 ))
            corners[0,:] = ( x[i,j,0,0],   y[i,j,0,0],   z[i,j,0,0]   )
            corners[1,:] = ( x[i,j,0,-1],  y[i,j,0,-1],  z[i,j,0,-1]  )
            corners[2,:] = ( x[i,j,-1,-1], y[i,j,-1,-1], z[i,j,-1,-1] )
            corners[3,:] = ( x[i,j,-1,0],  y[i,j,-1,0],  z[i,j,-1,0]  )

            # average the vectors formed by the corners to find f/s vects
            # the fast scan direction is the last index, s is next
            # f points left -> right, s points bottom -> top
            f = (( corners[1,:] - corners[0,:] ) + ( corners[2,:] - corners[3,:] ))
            s = (( corners[3,:] - corners[0,:] ) + ( corners[2,:] - corners[1,:] ))

            # make them pixel-size magnitude
            f = f * (pixel_size / np.linalg.norm(f))
            s = s * (pixel_size / np.linalg.norm(s))

            # center is just the average of the 4 corners
            c = np.mean( corners, axis=0 )
            assert c.shape == (3,)
            # c[2] += distance_offset

            bg.add_grid_using_center(c, s, f, shape)
            
    geom_instance = obj.from_basisgrid(bg)
                 
    return geom_instance


def write_cheetah(detector, filename="pixelmap-cheetah-raw.h5"):
    """
    docstring
    """

    coordinates = ['x', 'y', 'z']
    
    if not hasattr(detector, 'xyz'):
        raise TypeError('passed `detector` object must have an xyz attr')

    pp = np.squeeze(detector.xyz)
    if not pp.shape == (4, 8, 185, 388, 3):
        raise ValueError('Geometry does not appear to be a CSPAD. Expected xyz '
                         'shape (4, 8, 185, 388, 3), got: %s' % str(pp.shape))

    # write an h5
    f = h5py.File(filename, 'w')

    # iterate over x/y/z
    for xyz in range(len(coordinates)):

        cheetah_image = np.zeros((1480, 1552), dtype=np.float32)

        # iterate over each 2x1/quad (note switch)

        # new
        for q in range(4):
            for a in range(8): # which 2x1

                x_start = 388 * q
                x_stop  = 388 * (q+1)

                y_start = 185 * a
                y_stop  = 185 * (a + 1)

                # convert um --> m
                cheetah_image[y_start:y_stop,x_start:x_stop] = pp[q,a,:,:,xyz] / 1000000.0


        f['/%s' % coordinates[xyz]] = cheetah_image

    f.close()

    return
    

# ---- crystfel ---------------------------------------------------------------- 

def load_crystfel(obj, filename, verbose=False):
    """
    Convert a CrystFEL geom file to a CSPad object.

    Parameters
    ----------
    filename : str
        The path to the geom text file.

    Returns
    -------
    cspad : CSPad
        An CSPad object.
    """
    
    _check_obj(obj)
    
    # NOTE ON UNITS: all CrystFEL units are pixel units, except the
    # sample-to-detector offset
    
    if not filename.endswith('.geom'):
        raise IOError('Can only read flat text files with extension `.geom`.'
                      ' Got: %s' % filename)

    if verbose: print "Converting CSPAD geometry in: %s ..." % filename
    f = open(filename, 'r')
    geom_txt = f.read()
    f.close()

    # initialize an thor BasisGrid object -- will add ASICs to this
    bg = BasisGrid()
    shp = (185, 194) # this never changes for the CSPAD


    # measure the absolute detector offset
    # right now this appears to be the only z-information in the geometry...
    re_pz = re.search('coffset = (\d+.\d+..\d+)', geom_txt)
    if re_pz == None:
        print "WARNING: Could not find `coffset` field, defaulting z-offset to 0.0"
        p_z = 0.0
    else:
        p_z = float(re_pz.group(1)) / 1000.0 # m --> mm

    # iterate over each quad / ASIC
    for q in range(4):
        for a in range(16):

            if verbose:
                print "Reading geometry for: QUAD %d / ASIC %d" % (q, a)

            try:

                # match f/s vectors
                re_fs = re.search('q%da%d/fs =\s+((.)?\d+.\d+)x\s+((.)?\d+.\d+)y' % (q, a), geom_txt)
                f_x = float( re_fs.group(1) )
                f_y = float( re_fs.group(3) )
                f = np.array([f_x, f_y, 0.0])
                f = f * (pixel_size / np.linalg.norm(f))

                re_ss = re.search('q%da%d/ss =\s+((.)?\d+.\d+)x\s+((.)?\d+.\d+)y' % (q, a), geom_txt)
                s_x = float( re_ss.group(1) )
                s_y = float( re_ss.group(3) )
                s = np.array([s_x, s_y, 0.0])
                s = s * (pixel_size / np.linalg.norm(s))
                
            except AttributeError as e:
                print e
                raise IOError('Geometry file incomplete -- cant parse one or '
                              'more basis vector fields (ss/fs) QUAD %d / ASIC %d' % (q, a))

            # match corner postions, that become the p vector
            # note we have to convert from pixel units to mm
            # and also that CrystFEL measures the corner from the actual
            # *corner*, and not the center of the corner pixel!
            
            try:
                
                re_cx = re.search('q%da%d/corner_x =\s+((.)?\d+.\d+)' % (q, a), geom_txt)
                p_x = (float( re_cx.group(1) ) + 0.5) * pixel_size

                re_cy = re.search('q%da%d/corner_y =\s+((.)?\d+.\d+)' % (q, a), geom_txt)
                p_y = (float( re_cy.group(1) ) + 0.5) * pixel_size

                p = np.array([p_x, p_y, p_z])

            except AttributeError as e:
                print e
                raise IOError('Geometry file incomplete -- cant parse one or '
                              'more corner fields for QUAD %d / ASIC %d' % (q, a))

            # finally, add the ASIC to the thor basis grid
            bg.add_grid(p, s, f, shp)

    if verbose: print " ... successfully converted geometry."
    
    geom_instance = obj.from_basisgrid(bg)
    
    return geom_instance
    
    

def write_crystfel(detector, filename, intensity_file_type='cheetah'):
    """
    Write a CSPAD geometry to disk in CrystFEL format. Note that some fields
    will be written but left blank -- these are fields you probably should
    fill in before performing any computations in CrystFEL, but are information
    that psgeom has no handle on (e.g. detector gain).
    
    Thanks to Rick Kirian & Tom White for assistance with this function.
    
    Parameters
    ----------
    detector : cspad.CSPad
        The detector geometry to write to disk
        
    filname : str
        The name of file to write. Will end in '.dtc'
        
    Optional Parameters
    -------------------
    intensity_file_type : str, {'cheetah'}
        The kind of file this geometry file will be used with. Necessary to tell
        CrystFEL how intensity data map onto the detector
    """
    
    pixel_size = 0.10992 # in mm
    bg = detector.to_basisgrid()
    
    def get_sign(v):
        if v >= 0:
            s = '+'
        else:
            s = '-'
        return s
    
    
    if intensity_file_type == 'cheetah':
        
        # this is complex, so I went the lazy route and copied an
        # existing file
        intensity_map = crystfel_cheetah_intensities.split('-')
        assert len(intensity_map) == 64
        
    else:
        raise ValueError('Cannot write geometries for '
                        '`intensity_file_type`: %s, only currently '
                        'have implemented writers for '
                        '{"cheetah"}' % intensity_file_type)
    
    
    
    with open(filename, 'w') as of:
    
        print >> of, "; This file contains a CSPAD geometry generated by psgeom"
        print >> of, "; https://github.com/LinacCoherentLightSource/psgeom"
    
        header = """
; --- VALUES YOU MAY WANT TO FILL IN MANUALLY ---
; we cannot fill in these values for you :(

;clen = 
;coffset = 

;adu_per_eV = 
;max_adu = 

;mask = 
;mask_good = 
;mask_bad = 

;bad_jet/min_x = 
;bad_jet/max_x = 
;bad_jet/min_y = 
;bad_jet/max_y = 
; -----------------------------------------------


"""
        
        print >> of, header
        
        # iterate over each basis grid object
        for quad in range(4):
            for asic in range(16):
                
                grid_index = quad * 16 + asic
                p, s, f, sp = bg.get_grid(grid_index)
    
                panel_name = "q%da%d" % (quad, asic)
                
                # tell crystFEL how read intensity values in a file
                print >> of, intensity_map[grid_index].strip()
                
                # these are constant for the CSPAD
                print >> of, "%s/badrow_direction = -" % panel_name
                print >> of, "%s/res = 9097.525473" % panel_name
                
                # write the basis vectors           
                sqt = math.sqrt(f[0]**2 + f[1]**2) 
                print >> of, "%s/fs = %s%fx %s%fy" % ( panel_name,
                                                       get_sign(f[0]/sqt), abs(f[0]/sqt), 
                                                       get_sign(f[1]/sqt), abs(f[1]/sqt) )
                sqt = math.sqrt(s[0]**2 + s[1]**2)
                print >> of, "%s/ss = %s%fx %s%fy" % ( panel_name,
                                                       get_sign(s[0]/sqt), abs(s[0]/sqt), 
                                                       get_sign(s[1]/sqt), abs(s[1]/sqt) )
                
                # write the corner positions
                tagcx = "%s/corner_x" % panel_name
                tagcy = "%s/corner_y" % panel_name
            
                # CrystFEL measures the corner from the actual *corner*, and not
                # the center of the corner pixel, hence the 0.5's
                print >> of, "%s = %f" % (tagcx, float(p[0])/pixel_size - 0.5 )
                print >> of, "%s = %f" % (tagcy, float(p[1])/pixel_size - 0.5 )
                
                # this tells CrystFEL to use this panel
                print >> of, "%s/no_index = 0" % panel_name
                
                print >> of, "" # new line
    
    return    

    
    
# ---- generic text ------------------------------------------------------------
    
    
def write_psf_text(detector, filename):
    """
    Write a geometry to disk in the following format:
    
        p_x p_y p_z     s_x s_y s_z     f_x f_y f_z
        ...
        
    and include some comments.    
    
    
    Parameters
    ----------
    geometry : cspad.CSPad
        The detector geometry to write to disk
        
    filname : str
        The name of file to write. Will end in '.dtc'
    """
    
    # generate a preamble
    preamble = """
# This file contains a CSPAD geometry generated by psgeom: 
# https://github.com/LinacCoherentLightSource/psgeom
#
# The following is a basis grid representation with the following vectors
#
#   p : position vector for an ASIC
#   s : slow-scan pixel vector
#   f : fast-scan pixel vector
#
# all units are mm. Each ASIC is 185 x 194 pixels.
# See the psgeom documentation for more information.


#            p_x        p_y        p_z           s_x        s_y        s_z           f_x        f_y        f_z
"""

    # loop over each grid element and add it to the file
    bg = detector.to_basisgrid()
    body = ""
    
    
    def format(s, total_len=10):
        """
        A little formatting function
        """
        sf = '%.5f' % s
        pad = total_len - len(sf)
        if pad > 0:
            sf = ' ' * pad + sf
        return sf
        
    
    for i in range(bg.num_grids):
        
        # if we're starting a new quad, note that in the file
        if i % 16 == 0:
            body += ('\n# QUAD %d\n' % (i/16))
        
        # add the basis grid
        p, s, f, shp = bg.get_grid(i)
        strp = ' '.join( [ format(x) for x in p ] )
        strs = ' '.join( [ format(x) for x in s ] )
        strf = ' '.join( [ format(x) for x in f ] )
        
        tb = ' ' * 4
        asic = str(i)
        if len(asic) == 1:
            asic = ' ' + asic
        
        body += (asic + tb + strp + tb + strs + tb + strf + '\n')
        
    f = open(filename, 'w')
    f.write(preamble + body)
    f.close()
    
    print "Wrote CSPAD to text at: %s" % filename
    
    return
    
    




#  ---------- REFERENCE DATA ---------------------------------------------------


crystfel_cheetah_intensities = """q0a0/min_fs = 0
q0a0/min_ss = 0
q0a0/max_fs = 193
q0a0/max_ss = 184
-
q0a1/min_fs = 194
q0a1/min_ss = 0
q0a1/max_fs = 387
q0a1/max_ss = 184
-
q0a2/min_fs = 0
q0a2/min_ss = 185
q0a2/max_fs = 193
q0a2/max_ss = 369
-
q0a3/min_fs = 194
q0a3/min_ss = 185
q0a3/max_fs = 387
q0a3/max_ss = 369
-
q0a4/min_fs = 0
q0a4/min_ss = 370
q0a4/max_fs = 193
q0a4/max_ss = 554
-
q0a5/min_fs = 194
q0a5/min_ss = 370
q0a5/max_fs = 387
q0a5/max_ss = 554
-
q0a6/min_fs = 0
q0a6/min_ss = 555
q0a6/max_fs = 193
q0a6/max_ss = 739
-
q0a7/min_fs = 194
q0a7/min_ss = 555
q0a7/max_fs = 387
q0a7/max_ss = 739
-
q0a8/min_fs = 0
q0a8/min_ss = 740
q0a8/max_fs = 193
q0a8/max_ss = 924
-
q0a9/min_fs = 194
q0a9/min_ss = 740
q0a9/max_fs = 387
q0a9/max_ss = 924
-
q0a10/min_fs = 0
q0a10/min_ss = 925
q0a10/max_fs = 193
q0a10/max_ss = 1109
-
q0a11/min_fs = 194
q0a11/min_ss = 925
q0a11/max_fs = 387
q0a11/max_ss = 1109
-
q0a12/min_fs = 0
q0a12/min_ss = 1110
q0a12/max_fs = 193
q0a12/max_ss = 1294
-
q0a13/min_fs = 194
q0a13/min_ss = 1110
q0a13/max_fs = 387
q0a13/max_ss = 1294
-
q0a14/min_fs = 0
q0a14/min_ss = 1295
q0a14/max_fs = 193
q0a14/max_ss = 1479
-
q0a15/min_fs = 194
q0a15/min_ss = 1295
q0a15/max_fs = 387
q0a15/max_ss = 1479
-
q1a0/min_fs = 388
q1a0/min_ss = 0
q1a0/max_fs = 581
q1a0/max_ss = 184
-
q1a1/min_fs = 582
q1a1/min_ss = 0
q1a1/max_fs = 775
q1a1/max_ss = 184
-
q1a2/min_fs = 388
q1a2/min_ss = 185
q1a2/max_fs = 581
q1a2/max_ss = 369
-
q1a3/min_fs = 582
q1a3/min_ss = 185
q1a3/max_fs = 775
q1a3/max_ss = 369
-
q1a4/min_fs = 388
q1a4/min_ss = 370
q1a4/max_fs = 581
q1a4/max_ss = 554
-
q1a5/min_fs = 582
q1a5/min_ss = 370
q1a5/max_fs = 775
q1a5/max_ss = 554
-
q1a6/min_fs = 388
q1a6/min_ss = 555
q1a6/max_fs = 581
q1a6/max_ss = 739
-
q1a7/min_fs = 582
q1a7/min_ss = 555
q1a7/max_fs = 775
q1a7/max_ss = 739
-
q1a8/min_fs = 388
q1a8/min_ss = 740
q1a8/max_fs = 581
q1a8/max_ss = 924
-
q1a9/min_fs = 582
q1a9/min_ss = 740
q1a9/max_fs = 775
q1a9/max_ss = 924
-
q1a10/min_fs = 388
q1a10/min_ss = 925
q1a10/max_fs = 581
q1a10/max_ss = 1109
-
q1a11/min_fs = 582
q1a11/min_ss = 925
q1a11/max_fs = 775
q1a11/max_ss = 1109
-
q1a12/min_fs = 388
q1a12/min_ss = 1110
q1a12/max_fs = 581
q1a12/max_ss = 1294
-
q1a13/min_fs = 582
q1a13/min_ss = 1110
q1a13/max_fs = 775
q1a13/max_ss = 1294
-
q1a14/min_fs = 388
q1a14/min_ss = 1295
q1a14/max_fs = 581
q1a14/max_ss = 1479
-
q1a15/min_fs = 582
q1a15/min_ss = 1295
q1a15/max_fs = 775
q1a15/max_ss = 1479
-
q2a0/min_fs = 776
q2a0/min_ss = 0
q2a0/max_fs = 969
q2a0/max_ss = 184
-
q2a1/min_fs = 970
q2a1/min_ss = 0
q2a1/max_fs = 1163
q2a1/max_ss = 184
-
q2a2/min_fs = 776
q2a2/min_ss = 185
q2a2/max_fs = 969
q2a2/max_ss = 369
-
q2a3/min_fs = 970
q2a3/min_ss = 185
q2a3/max_fs = 1163
q2a3/max_ss = 369
-
q2a4/min_fs = 776
q2a4/min_ss = 370
q2a4/max_fs = 969
q2a4/max_ss = 554
-
q2a5/min_fs = 970
q2a5/min_ss = 370
q2a5/max_fs = 1163
q2a5/max_ss = 554
-
q2a6/min_fs = 776
q2a6/min_ss = 555
q2a6/max_fs = 969
q2a6/max_ss = 739
-
q2a7/min_fs = 970
q2a7/min_ss = 555
q2a7/max_fs = 1163
q2a7/max_ss = 739
-
q2a8/min_fs = 776
q2a8/min_ss = 740
q2a8/max_fs = 969
q2a8/max_ss = 924
-
q2a9/min_fs = 970
q2a9/min_ss = 740
q2a9/max_fs = 1163
q2a9/max_ss = 924
-
q2a10/min_fs = 776
q2a10/min_ss = 925
q2a10/max_fs = 969
q2a10/max_ss = 1109
-
q2a11/min_fs = 970
q2a11/min_ss = 925
q2a11/max_fs = 1163
q2a11/max_ss = 1109
-
q2a12/min_fs = 776
q2a12/min_ss = 1110
q2a12/max_fs = 969
q2a12/max_ss = 1294
-
q2a13/min_fs = 970
q2a13/min_ss = 1110
q2a13/max_fs = 1163
q2a13/max_ss = 1294
-
q2a14/min_fs = 776
q2a14/min_ss = 1295
q2a14/max_fs = 969
q2a14/max_ss = 1479
-
q2a15/min_fs = 970
q2a15/min_ss = 1295
q2a15/max_fs = 1163
q2a15/max_ss = 1479
-
q3a0/min_fs = 1164
q3a0/min_ss = 0
q3a0/max_fs = 1357
q3a0/max_ss = 184
-
q3a1/min_fs = 1358
q3a1/min_ss = 0
q3a1/max_fs = 1551
q3a1/max_ss = 184
-
q3a2/min_fs = 1164
q3a2/min_ss = 185
q3a2/max_fs = 1357
q3a2/max_ss = 369
-
q3a3/min_fs = 1358
q3a3/min_ss = 185
q3a3/max_fs = 1551
q3a3/max_ss = 369
-
q3a4/min_fs = 1164
q3a4/min_ss = 370
q3a4/max_fs = 1357
q3a4/max_ss = 554
-
q3a5/min_fs = 1358
q3a5/min_ss = 370
q3a5/max_fs = 1551
q3a5/max_ss = 554
-
q3a6/min_fs = 1164
q3a6/min_ss = 555
q3a6/max_fs = 1357
q3a6/max_ss = 739
-
q3a7/min_fs = 1358
q3a7/min_ss = 555
q3a7/max_fs = 1551
q3a7/max_ss = 739
-
q3a8/min_fs = 1164
q3a8/min_ss = 740
q3a8/max_fs = 1357
q3a8/max_ss = 924
-
q3a9/min_fs = 1358
q3a9/min_ss = 740
q3a9/max_fs = 1551
q3a9/max_ss = 924
-
q3a10/min_fs = 1164
q3a10/min_ss = 925
q3a10/max_fs = 1357
q3a10/max_ss = 1109
-
q3a11/min_fs = 1358
q3a11/min_ss = 925
q3a11/max_fs = 1551
q3a11/max_ss = 1109
-
q3a12/min_fs = 1164
q3a12/min_ss = 1110
q3a12/max_fs = 1357
q3a12/max_ss = 1294
-
q3a13/min_fs = 1358
q3a13/min_ss = 1110
q3a13/max_fs = 1551
q3a13/max_ss = 1294
-
q3a14/min_fs = 1164
q3a14/min_ss = 1295
q3a14/max_fs = 1357
q3a14/max_ss = 1479
-
q3a15/min_fs = 1358
q3a15/min_ss = 1295
q3a15/max_fs = 1551
q3a15/max_ss = 1479"""

