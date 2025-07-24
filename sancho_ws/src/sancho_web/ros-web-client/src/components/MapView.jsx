import React, { useContext, useEffect, useRef } from 'react';
import { RosContext } from '../ros/RosContext';

/**
 * MapView Component.
 *
 * This component sets up a ROS3D viewer for displaying a robotics map along with dynamic visual markers.
 * It subscribes to the following ROS topics:
 * - '/map' for rendering an occupancy grid representing the map.
 * - '/amcl_pose' to update a red cube indicating the robot's current pose.
 * - '/move_base_simple/goal' to display a green arrow showing the target goal position.
 *
 * The viewer is initialized with default dimensions and scene settings. Upon receiving pose data,
 * the component updates the position and orientation of the red cube. Similarly, when a goal is received,
 * the green arrow is positioned and oriented accordingly.
 *
 * All subscriptions and visual elements are cleaned up when the component unmounts.
 *
 * Dependencies:
 * - ROS3D for 3D visualization.
 * - ROSLIB for ROS topic communication.
 * - THREE for 3D object creation and manipulation.
 *
 * @component
 * @example
 * // Render the MapView component as part of your layout
 * <MapView />
 */
export default function MapView() {
  const { ros } = useContext(RosContext);
  const viewerRef = useRef(null);
  const poseBoxRef = useRef(null);
  const goalArrowRef = useRef(null);

  useEffect(() => {
    if (!ros || !viewerRef.current || !window.ROS3D || !window.ROSLIB) return;

    const ROS3D = window.ROS3D;
    const ROSLIB = window.ROSLIB;
    const THREE = window.THREE;

    // Inicializamos el viewer
    const divId = 'map-canvas-viewer';
    viewerRef.current.id = divId;
    const viewer = new ROS3D.Viewer({
      divID: divId,
      width: viewerRef.current.clientWidth || 800,
      height: 400,
      antialias: true,
    });



    // Carga del mapa
    const gridClient = new ROS3D.OccupancyGridClient({
      ros,
      rootObject: viewer.scene,
      continuous: true,
      topic: '/map',
    });

    // —–––– CAJITA ROJA DEL ROBOT –––––—
    const size = 0.3;
    const boxGeometry = new THREE.BoxBufferGeometry(size, size, size);
    const boxMat = new THREE.MeshBasicMaterial({
      color: 0xff0000,
      depthTest: true,  // siempre encima del mapa
      wireframe: false,  // activa true para depurar aristas
    });
    const poseBox = new THREE.Mesh(boxGeometry, boxMat);
    poseBox.visible = false;
    viewer.scene.add(poseBox);
    poseBoxRef.current = poseBox;

    const goalArrow = new ROS3D.Arrow({
      shaftRadius: 0.1,
      headRadius: 0.2,
      headLength: 0.3,
      length: 1,
      material: new THREE.MeshBasicMaterial({
        color: 0x00ff00,
        depthTest: false
      }),
    });
    goalArrow.visible = false;
    viewer.scene.add(goalArrow);
    goalArrowRef.current = goalArrow;

    // Suscripción a la pose del robot
    const poseSub = new ROSLIB.Topic({
      ros,
      name: '/amcl_pose',
      messageType: 'geometry_msgs/PoseWithCovarianceStamped',
    });
    poseSub.subscribe(msg => {
      const { x, y } = msg.pose.pose.position;
      const q = msg.pose.pose.orientation;
      const quaternion = new THREE.Quaternion(q.x, q.y, q.z, q.w);

      poseBox.visible = true;
      poseBox.position.set(x, y, 0);
      poseBox.setRotationFromQuaternion(quaternion);
    });

    const goalSub = new ROSLIB.Topic({
      ros,
      name: '/move_base_simple/goal',
      messageType: 'geometry_msgs/PoseStamped',
    });
    goalSub.subscribe(msg => {
      const { x, y } = msg.pose.position;
      const q = msg.pose.orientation;
      const quaternion = new THREE.Quaternion(q.x, q.y, q.z, q.w);

      goalArrow.visible = true;
      goalArrow.position.set(x, 0.1, -y);
      goalArrow.setRotationFromQuaternion(quaternion);
    });

    // Limpieza al desmontar
    return () => {
      gridClient.unsubscribe();
      poseSub.unsubscribe();
      goalSub.unsubscribe();
      if (viewerRef.current) {
        viewerRef.current.innerHTML = '';
      }

    };
  }, [ros]);

  return (
    <div
      id="map-canvas"
      ref={viewerRef}
      className="border rounded shadow w-100"
      style={{ height: '400px' }}
    />
  );
}
