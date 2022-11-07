from scipy.interpolate import splprep, splev
import numpy as np

def imshow(axis, img):
    ''' Show greyscale image without axis
    :param axis: matplotlib axis
    :param img: 2D image to display
    '''
    axis.imshow(img, cmap='gray')
    axis.axis('off')


def clear_figures(axes):
    ''' Clear plots from axes
    :param axes: list of matplotlib axes 
    '''
    for axis in axes:
        axis.cla()


def roishow(axis, endo_contours, epi_contours, orientation):
    ''' Show ROI contours on a given plot
    :param axis: matplotlib axis (can have something plotted already)
    :param endo_contours: endo contour coordinates from n points -> (2, n)
    :param epi_contours: epi contour coordinates from n points -> (2, n)
    :param orientation: "SA" or "LA"
    '''
    # If short-axis, plot the two contours
    if orientation == 'SA':
        axis.plot(epi_contours[0], epi_contours[1], c='red')
        axis.plot(endo_contours[0], endo_contours[1], c='red')
    # Otherwise, consider it a single closed contour and plot
    elif orientation == 'LA':
        contours = np.concatenate([epi_contours, endo_contours, epi_contours[:, 0:1]], axis=1)
        axis.plot(contours[0], contours[1], c='red')
    else:
        raise ValueError('ROI orientation axis should be either SA or LA.')


def anchor_to_contour(orientation, endo_points, epi_points):
    ''' From a few anchor points, extrapolate "continuous" contours
    :param orientation: "SA" or "LA"
    :param endo_points: m endo anchor point coordinates (m, 2) (gen. from Matlab, starts from 1)
    :param epi_points: m epi anchor point coordinates (m, 2) (gen. from Matlab, starts from 1)
    '''
    # If short-axis, add back first point at the end to obtain a closed interpolation
    if orientation == 'SA':
        epi_points = np.concatenate([epi_points, epi_points[0:1]], axis=0)
        endo_points = np.concatenate([endo_points, endo_points[0:1]], axis=0)
        closed = True
    elif orientation == 'LA':
        closed = False
    else:
        raise ValueError('ROI orientation axis should be either SA or LA')

    # Consider coordinates - 1 because assumes it comes from Matlab
    # 100 points interpolation
    endo_interp, _ = splprep([endo_points[:,0]-1, endo_points[:,1]-1], s=0, per=closed)
    endo_sampling = np.arange(0, 1.01, 0.01)
    endo_contour = splev(endo_sampling, endo_interp)

    epi_interp, _ = splprep([epi_points[:,0]-1, epi_points[:,1]-1], s=0, per=closed)
    epi_sampling = np.arange(0, 1.01, 0.01)
    epi_contour = splev(epi_sampling, epi_interp)

    return np.array(endo_contour), np.array(epi_contour)