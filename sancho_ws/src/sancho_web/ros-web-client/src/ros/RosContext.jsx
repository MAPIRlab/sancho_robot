// src/ros/RosContext.jsx
import React, { createContext, useState, useEffect, useRef, useCallback } from 'react';
import ROSLIB from 'roslib';
import { toast } from 'react-toastify';

export const RosContext = createContext({
  ros: /** @type {import('roslib').Ros|null} */ (null),
  isConnected: false,
  connect: /** @type {()=>void} */ (() => { }),
  disconnect: /** @type {()=>void} */ (() => { }),
});

export const RosProvider = ({ children }) => {
  const rosRef = useRef(/** @type {ROSLIB.Ros|null} */(null));
  const reconnectAttempts = useRef(0);
  const [isConnected, setIsConnected] = useState(false);

  const connect = useCallback(() => {
    console.log('Intentando conectar a ROSBridge...');
    const url =
      localStorage.getItem('rosbridge_url') ||
      'ws://150.214.109.170:9090';

    const ros = new ROSLIB.Ros({ url });
    rosRef.current = ros;

    ros.on('connection', () => {

      reconnectAttempts.current = 0;
      setIsConnected(true);
      toast.success('🚀 Conectado a ROSBridge');
    });

    ros.on('error', (err) => {
      console.error('ROSBridge Error:', err);
      // Solo toast de error si ya estabas conectado antes
      if (isConnected) {
        toast.error(`❌ Error ROSBridge: ${err.message || err}`);
      }
    });

    ros.on('close', () => {
      if (isConnected) {
        toast.warn('⚠️ Desconectado de ROSBridge');
      }
      setIsConnected(false);
      // Reconexión automática con backoff exponencial
      const delay = Math.min(30000, 1000 * 2 ** reconnectAttempts.current);
      reconnectAttempts.current += 1;
      // setTimeout(connect, delay); // Descomentarlo PARA reconectar automáticamente
    });
    console.log(`Conectando a ${url}...`);
  }, []);

  const disconnect = useCallback(() => {
    rosRef.current?.close();
    reconnectAttempts.current = 0;
    setIsConnected(false);
  }, []);

  // Iniciar conexión al montar
  useEffect(() => {
    connect();
    return () => disconnect();
  }, []);

  return (
    <RosContext.Provider
      value={{
        ros: rosRef.current,
        isConnected,
        connect,
        disconnect,
      }}
    >
      {children}
    </RosContext.Provider>
  );
};
