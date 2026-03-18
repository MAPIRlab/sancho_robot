import numpy as np

class HopfieldQPSolver:
    """
    Hopfield Neural Network for solving Quadratic Programming (QP).
    Optimized for integration in ROS nodes.
    
    Minimize: 0.5 * x.T @ Q @ x + c.T @ x
    Subject to: G @ x <= h
    """
    def __init__(self, Q, c, G=None, h=None):
        self.Q = np.array(Q)
        self.c = np.array(c).reshape(-1, 1)
        self.G = np.array(G) if G is not None else None
        self.h = np.array(h).reshape(-1, 1) if h is not None else None
        self.n = len(c)

    def _gradient(self, x, rho_ineq):
        x = x.reshape(-1, 1)
        # Gradient of objective
        grad = self.Q @ x + self.c
        
        # Penalty for inequalities Gx <= h
        if self.G is not None:
            viol = self.G @ x - self.h
            # ReLu for penalty: rho * G.T @ max(0, Gx - h)
            viol[viol < 0] = 0
            grad += rho_ineq * self.G.T @ viol
            
        return grad

    def solve(self, x0=None, eta=0.001, max_steps=500, tol=1e-4, rho=500.0):
        if x0 is None:
            x = np.zeros((self.n, 1))
        else:
            x = np.array(x0).reshape(-1, 1).astype(float)
            
        for _ in range(max_steps):
            grad = self._gradient(x, rho)
            dx = -eta * grad
            x += dx
            if np.linalg.norm(dx) < tol:
                break
        return x.flatten()
