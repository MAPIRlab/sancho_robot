std_msgs/Header header
uint32 id
float32[34] keypoints         # 2D: [x0, y0, x1, y1, ..., x16, y16]
float32[51] keypoints3d       # 3D: [x0,y0,z0, x1,y1,z1, ..., x16,y16,z16]
float32[17] scores
float32 avg_depth
