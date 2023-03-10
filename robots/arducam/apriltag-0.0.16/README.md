
Apriltag
--------
apriltag marker detection
based on <https://github.com/swatbotics/apriltag>

Dependencies
------------

  - OpenCV (optional)

Example
-------
```python
import apriltag
import cv2
img = cv2.imread('apriltag_foto.jpg'.cv2.IMREAD_GRAYSCALE)
detector = apriltag.Detector()
result = detector.detect(img)
```


result is in the form of
```
[DetectionBase(tag_family='tag36h11', tag_id=2, hamming=0, goodness=0.0, decision_margin=98.58241271972656, homography=array([[ -1.41302664e-01,   1.08428082e+00,   1.67512900e+01],
   [ -8.75899366e-01,   1.50245469e-01,   1.70532040e+00],
   [ -4.89183533e-04,   2.12210247e-03,   6.02052342e-02]]), center=array([ 278.23643912,   28.32511859]), corners=array([[ 269.8939209 ,   41.50381088],
   [ 269.57183838,   11.79248142],
   [ 286.1383667 ,   15.84242821],
   [ 286.18066406,   43.48323059]])),
DetectionBase(tag_family='tag36h11', ... etc
```


Multiple options can be specified to tune the detection performance:
--------------------------------------------------------------------
```python
options = apriltag.Detectoroptions(families='tag36h11',
                                 border=1,
                                 nthreads=4,
                                 quad_decimate=1.0,
                                 quad_blur=0.0,
                                 refine_edges=True,
                                 refine_decode=False,
                                 refine_pose=False,
                                 debug=False,
                                 quad_contours=True)
detector = apriltag.Detector()
result = detector.detect(img)
```

Access values
--------
```python
tf = result[0].tag_family
cx = result[0].center[0]
.
