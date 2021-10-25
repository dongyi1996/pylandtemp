import numpy as np 
from emissivity.utils import fractional_vegetation_cover, cavity_effect


EMISSIVITY_METHODS = ['avdan', 'xiaolei', 'gopinadh']

class Emissivity:

    def __init__(self, ndvi, red_band=None):
        self.ndvi = ndvi
        self.red_band = red_band
    
    def __call__(self, method):
        assert method in EMISSIVITY_METHODS, ValueError("Method not implemented")
        compute_method = self.get_method(method)

        return compute_method(self.ndvi, self.red_band)()


    def get_method(self, method):

        if method == 'avdan':
            return ComputeMonoWindowEmissivity
        elif method == 'xiaolei':
            return ComputeEmissivityNBEM
        elif method == 'gopinadh':
            return ComputeEmissivityGopinadh
        else:
            raise NotImplementedError("Requested method not implemented. Choose among available methods: {EMMISIVITY_METHODS}")

        


class EmissivityParent:
    def __init__(self, ndvi, red_band):
        """[summary]

        Args:
            ndvi (np.ndarray[float]): Normalized difference vegetation index in matrix form

        """
        assert len(ndvi.shape) == 2, ValueError("Input must be single band image with two dimensions only. {}".format(ndvi.shape))
        self.ndvi = ndvi #nvdi image
        self.red_band = red_band
        self.emissivity = np.zeros_like(ndvi) 
        self.nan_mask = np.isnan(ndvi) # mask for nan values 

    def __call__(self):

        if self.red_band is not None:
            assert self.ndvi.shape == self.red_band.shape , ValueError("Input images (NDVI and Red band) must be of equal dimension")

        emm = self._compute_emissivity()

        emm[self.nan_mask] = np.nan

        return emm
        
        
    def _get_land_surface_mask(self):
        
        mask_baresoil = (self.ndvi >= -1) & (self.ndvi < 0.2)
        mask_vegetation = (self.ndvi > 0.5) & (self.ndvi <= 1)
        mask_mixed = (self.ndvi >= 0.2) & (self.ndvi <= 0.5)

        return {
                'baresoil': mask_baresoil, 
                'vegetation': mask_vegetation, 
                'mixed': mask_mixed
                }

    def _compute_emissivity(self):
        raise NotImplementedError("No emissivity computation logic implemented yet")
    


    def _compute_cavity_effect(self):
        """Computes cavity effect from fractional vegetation cover matrix

        Args:
            frac_vegetation_cover (np.ndarray): Fractional vegetation cover matrix

        Returns:
            np.ndarray: Cavity effect matric
        """
        fractional_veg_cover = self._compute_fvc()
        return  cavity_effect(fractional_veg_cover)

    def _get_landcover_mask_indices(self):
        """Returns indices corresponding to the different landcover classes of of interest namely:
            vegetation, baresoil and mixed"

        Args:
            landcover ([type]): [description]
        """

        masks = self._get_land_surface_mask()

        # Baresoil value assignment
        baresoil = np.where(masks['baresoil'])
        vegetation = np.where(masks['vegetation'])
        mixed = np.where(masks['mixed'])

        return {'baresoil': baresoil, 'vegetation': vegetation, 'mixed': mixed}

    def _compute_fvc(self):
    #    raise NotImplementedError("Fractional vegetation cover computation not implemented yet, or not applied")
        return fractional_vegetation_cover(self.ndvi)
        


class ComputeMonoWindowEmissivity(EmissivityParent):
    
    def __init__(self, ndvi, red_band=None):
        super(ComputeMonoWindowEmissivity, self).__init__(ndvi, red_band)
        self.emissivity_soil = 0.97 
        self.emissivity_veg = 0.99

    def _compute_emissivity(self):

        
        landcover_mask_indices = self._get_landcover_mask_indices()

        # Baresoil value assignment
        self.emissivity[landcover_mask_indices['baresoil']] = self.emissivity_soil

        # Vegetation value assignment
        self.emissivity[landcover_mask_indices['vegetation']] = self.emissivity_veg

        # Mixed value assignment
        self.emissivity[landcover_mask_indices['mixed']] = ((0.004 *
                                                            (((self.ndvi[landcover_mask_indices['mixed']] - 
                                                            0.2)/(0.5 - 0.2))**2)) +
                                                            0.986
        )

        self.emissivity[self.nan_mask] = np.nan

        return self.emissivity

 
    

class ComputeEmissivityNBEM(EmissivityParent):


    def __init__(self, ndvi, red_band):
        """
        Method references:

        1. Li, Tianyu, and Qingmin Meng. "A mixture emissivity analysis method for 
            urban land surface temperature retrieval from Landsat 8 data." Landscape 
            and Urban Planning 179 (2018): 63-71.
        
        2. Yu, Xiaolei, Xulin Guo, and Zhaocong Wu. "Land surface temperature retrieval 
            from Landsat 8 TIRS—Comparison between radiative transfer equation-based method, 
            split window algorithm and single channel method." Remote sensing 6.10 (2014): 9829-9852.

        
        Args:
            ndvi (np.ndarray[float]): Normalized difference vegetation index (NDVI) image matrix
            red_band (np.ndarray[float]): Red band of image (0.63-0.69 micrometers)
        """
        super(ComputeEmissivityNBEM, self).__init__(ndvi, red_band)
        self.emissivity_soil = 0.9668 
        self.emissivity_veg = 0.9863


    
    def _compute_emissivity(self):
        
        assert self.red_band is not None, \
            ValueError("Red band cannot be {} for this emissivity computation method".format(self.red_band))

        landcover_mask_indices = self._get_landcover_mask_indices()

        fractional_veg_cover = self._compute_fvc()

        cavity_effect_10 = self._compute_cavity_effect()    

        self.emissivity[landcover_mask_indices['baresoil']] = (0.973 - 
                                                                (0.047 * 
                                                                self.red_band[landcover_mask_indices['baresoil']])
        )

        self.emissivity[landcover_mask_indices['mixed']] = ((self.emissivity_veg * 
                                                            fractional_veg_cover[landcover_mask_indices['mixed']]) + 
                                                            (self.emissivity_soil *
                                                            (1 - fractional_veg_cover[landcover_mask_indices['mixed']])) +
                                                            cavity_effect_10[landcover_mask_indices['mixed']]
        )

        self.emissivity[landcover_mask_indices['vegetation']] = (self.emissivity_veg + 
                                                                cavity_effect_10[landcover_mask_indices['vegetation']]
        )

        self.emissivity[self.nan_mask] = np.nan

        return self.emissivity
    
    
    

class ComputeEmissivityGopinadh(EmissivityParent):

    def __init__(self, ndvi, red_band=None):
        """
        Method reference:

        Rongali, Gopinadh, et al. "Split-window algorithm for retrieval of land surface temperature 
        using Landsat 8 thermal infrared data." Journal of Geovisualization and Spatial Analysis 2.2 
        (2018): 1-19.

        Args:
            ndvi (np.ndarray[float]): Normalized difference vegetation index (NDVI) image matrix
            red_band (np.ndarray[float]): Red band of image (0.63-0.69 micrometers). Defaults to None.
        """
        super(ComputeEmissivityGopinadh, self).__init__(ndvi, red_band)
        self.emissivity_soil = 0.9668
        self.emissivity_veg = 0.9747
    
    def _compute_emissivity(self):
    
        fractional_veg_cover = self._compute_fvc()

        self.emissivity = ((self.emissivity_soil * 
                            (1 - fractional_veg_cover)) + 
                            (self.emissivity_veg * 
                            fractional_veg_cover))

        self.emissivity[self.nan_mask] = np.nan

        return  self.emissivity




