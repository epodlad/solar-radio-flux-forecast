"""New documented models, not a bitwise reconstruction of unavailable legacy code."""
from dataclasses import dataclass, asdict
import copy
import math
import numpy as np

@dataclass(frozen=True)
class Config:
    drift_alpha: float = 0.45
    variance_alpha: float = 0.05
    measurement_variance: float = 4.0
    initial_process_variance: float = 25.0
    process_floor: float = 0.01
    regression_alpha: float = 0.45
    coefficient_diffusion: float = 0.01
    def __post_init__(self):
        for x in (self.drift_alpha, self.variance_alpha, self.regression_alpha):
            if not 0 < x <= 1: raise ValueError('smoothing weight must be in (0,1]')
        for x in (self.measurement_variance, self.initial_process_variance, self.process_floor, self.coefficient_diffusion):
            if not math.isfinite(x) or x <= 0: raise ValueError('variances must be finite and positive')
    def json(self): return asdict(self)


def point(mean, variance):
    sd = math.sqrt(max(float(variance), 0))
    return {'mean_sfu': float(mean), 'sd_sfu': sd,
            'interval68_sfu': [float(mean)-sd, float(mean)+sd],
            'interval95_sfu': [float(mean)-1.95996398454*sd, float(mean)+1.95996398454*sd]}


class DriftFilter:
    """Scalar random walk; EWMA daily drift and innovation-based process variance."""
    name = 'adaptive_drift'
    def __init__(self, config=Config()):
        self.c = config
        self.x = self.previous = None
        self.p = config.measurement_variance
        self.q = config.initial_process_variance
        self.drift = 0.
        self.n = 0
    def update(self, y):
        if not math.isfinite(y): raise ValueError('nonfinite observation')
        if self.x is None:
            self.x = self.previous = float(y)
        else:
            pred = self.x + self.drift
            pp = self.p + self.q
            innovation = y - pred
            gain = pp / (pp + self.c.measurement_variance)
            old_p = self.p
            self.x = pred + gain * innovation
            self.p = (1-gain)**2 * pp + gain**2 * self.c.measurement_variance
            # Estimate Q for the NEXT step. This cannot change the already issued prediction.
            estimate = max(self.c.process_floor, innovation**2-old_p-self.c.measurement_variance)
            self.q = max(self.c.process_floor, (1-self.c.variance_alpha)*self.q+self.c.variance_alpha*estimate)
            self.drift += self.c.drift_alpha * ((y-self.previous)-self.drift)
            self.previous = float(y)
        self.n += 1
    def forecast(self, horizons=(1, 2, 3)):
        if self.x is None: raise ValueError('model has no observations')
        return [point(self.x+h*self.drift, self.p+h*self.q+self.c.measurement_variance) for h in horizons]
    def corrected(self, measurement, dt):
        """Experimental scalar late-day update, 0<dt<1, drift held fixed.

        Q scales linearly with elapsed days (new diffusion convention).
        Do not use an intraday increment as a daily drift observation.
        """
        if not 0 < dt < 1: raise ValueError('late update must be within same day')
        obj = copy.deepcopy(self)
        pp = obj.p+dt*obj.q
        pred = obj.x+dt*obj.drift
        k = pp/(pp+obj.c.measurement_variance)
        obj.x = pred+k*(measurement-pred)
        obj.p = (1-k)**2*pp+k*k*obj.c.measurement_variance
        return obj


class RegressionFilter:
    """Kalman coefficients for y_next = a0 + a1*y + a2*smoothed_increment.

    Internal features divide flux/increment by 100 for conditioning, with
    corresponding coefficient scaling. Multi-day covariance uses a documented
    first-order joint-state approximation; it is a new extension.
    """
    name = 'adaptive_regression'
    def __init__(self, config=Config()):
        self.c = config
        self.beta = np.array([0., 100., 0.])
        self.p = np.diag([100., 100., 100.])
        self.qbeta = np.eye(3)*config.coefficient_diffusion
        self.residual = config.initial_process_variance
        self.y = None
        self.delta = 0.
        self.n = 0
    def features(self): return np.array([1., self.y/100., self.delta/100.])
    def update(self, y):
        if not math.isfinite(y): raise ValueError('nonfinite observation')
        if self.y is not None:
            phi = self.features()  # strictly PREVIOUS day's features
            pp = self.p+self.qbeta
            innovation = y-float(phi@self.beta)
            r = self.residual+self.c.measurement_variance
            s = float(phi@pp@phi+r)
            k = pp@phi/s
            self.beta += k*innovation
            a = np.eye(3)-np.outer(k, phi)
            self.p = a@pp@a.T+np.outer(k,k)*r
            self.p = (self.p+self.p.T)/2
            estimate = max(self.c.process_floor, innovation**2-float(phi@pp@phi)-self.c.measurement_variance)
            self.residual = max(self.c.process_floor,(1-self.c.variance_alpha)*self.residual+self.c.variance_alpha*estimate)
            self.delta += self.c.regression_alpha*((y-self.y)-self.delta)
        self.y = float(y)
        self.n += 1
    def forecast(self, horizons=(1,2,3)):
        if self.y is None: raise ValueError('model has no observations')
        if any(h != int(h) or h<1 for h in horizons): raise ValueError('integer daily horizons only')
        state = np.r_[self.beta,self.y,self.delta]
        cov = np.zeros((5,5)); cov[:3,:3] = self.p
        results = {}
        a = self.c.regression_alpha
        for h in range(1,max(horizons)+1):
            # Coefficients diffuse before each future transition.
            cov[:3,:3] += self.qbeta
            b0,b1,b2,y,d = state
            phi = np.array([1,y/100,d/100])
            pred = float(phi@state[:3])
            grad = np.r_[phi,b1/100,b2/100]
            jac = np.eye(5); jac[3] = grad
            jac[4] = a*grad; jac[4,3] -= a; jac[4,4] += 1-a
            noise = np.array([0,0,0,1,a])
            cov = jac@cov@jac.T+np.outer(noise,noise)*self.residual
            cov = (cov+cov.T)/2
            state[3] = pred; state[4] = (1-a)*d+a*(pred-y)
            results[h] = point(pred,cov[3,3]+self.c.measurement_variance)
        return [results[h] for h in horizons]
