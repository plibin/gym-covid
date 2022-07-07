from gym.envs.registration import register
from gym.wrappers import TimeLimit
from gym_covid.envs.model import ODEModel, BinomialModel
from gym_covid.envs.epi_env import EpiEnv
from gym_covid.envs.discrete_actions import DiscreteAction
from gym_covid.envs.lockdown import Lockdown
import numpy as np
import pandas as pd
import json
from pathlib import Path
from importlib_resources import files, as_file
import datetime
import gym


def be_config():
    resources = files('gym_covid')    
    config_file = 'config/wave1.json'
    with open(resources / config_file, 'r') as f:
        config = json.load(f)

    contact_types = ['home', 'work', 'transport', 'school', 'leisure', 'otherplace']
    csm = [pd.read_csv(resources / config['social_contact_dir'] / f'{ct}.csv', header=None).values for ct in contact_types]
    csm = np.array(csm)

    ## set paths correctly for 'population' and 'cases' items
    config['cases'] = resources / config['cases']
    config['population'] = resources / config['population']

    ## DATAPOINTS
    df = pd.read_csv(resources / config['deaths'])
    df = df.sort_values('DATE')
    df = df[df['PLACE'] != 'Nursing home']
    df = df.groupby('DATE').agg('count')
    deaths = df['ID'].values
    # startdate is 10/03/22
    deaths = np.concatenate((np.zeros(9), deaths))

    df = pd.read_csv(resources / config['hospitalizations'])
    hospitalization = df['NewPatientsNotReferredHospital'].values.flatten()
    #startdate is 08/03/22
    hospitalization = np.concatenate((np.zeros(7), hospitalization))

    datapoints = {
        'hospitalizations': hospitalization,
        'deaths': deaths,
        }

    return config, csm, datapoints


def be_ode():
    config, csm, datapoints = be_config()
    model = ODEModel.from_config(config)
    env = EpiEnv(model, C=csm, beta_0=config['beta_0'], beta_1=config['beta_1'], datapoints=datapoints)
    return env


def be_binomial():
    config, csm, datapoints = be_config()
    model = BinomialModel.from_config(config)
    env = EpiEnv(model, C=csm, beta_0=config['beta_0'], beta_1=config['beta_1'], datapoints=datapoints)
    return env


def until_2020_09_01(env):
    end = datetime.date(2020, 9, 1)
    timesteps = round((end-env.today).days/env.days_per_timestep)
    return TimeLimit(env, timesteps)


def until_2021_01_01(env):
    end = datetime.date(2021, 1, 1)
    timesteps = round((end-env.today).days/env.days_per_timestep)
    return TimeLimit(env, timesteps)


def discretize_actions(env, work=None, school=None, leisure=None):
    if work is None:
        work = np.array([0, 30, 60])/100
    if school is None:
        school = np.array([0, 50, 100])/100
    if leisure is None:
        leisure = np.array([30, 60, 90])/100
    # all combinations of work, school, leisure
    actions = np.meshgrid(work, school, leisure)
    actions = np.stack(actions).reshape(3, -1).T
    return DiscreteAction(env, actions)


class EndPenalty(gym.Wrapper):
    d_I_limit = 0.5
    d_I_penalty = 1e6

    def step(self, action):
        s, r, t, info = super(EndPenalty, self).step(action)
        # if terminal, continue executing with no social contact for penalty
        if t:
            I = s[0][:, self.env.model.I_hosp] + s[0][:, self.env.model.I_icu]
            # over all age groups
            I = I.sum(1)
            # compute slope: (y2-y1)/(x2-x1)
            # assume x2-x1=1
            d_I = I[-1]-I[0]
            # if slope too high (meaning next wave is coming up), add penalty
            if d_I >= EndPenalty.d_I_limit:
                r[1] -= EndPenalty.d_I_penalty
                # print(f'slope : {d_I} too high, adding penalty')
            # # match all C components, reshape to match C shape
            # p = np.array([0, 0, 0, 0, 0, 0])[:, None, None]
            # C_asym = self.env.C*p
            # C_sym = (C_asym*self.env.C_sym_factor)
            # I_h = 1
            # # S_s = s[0][-1, self.env.model.S].sum()
            # penalty = 0
            # days = 0
            # while I_h >= 1:
            #     s_n = self.env.model.simulate_day(C_asym.sum(axis=0), C_sym.sum(axis=0))
            #     I_h = np.sum(s_n[self.env.model.I_hosp] + s_n[self.env.model.I_icu])
            #     penalty += I_h
            #     # print(days, s_n[self.env.model.I_hosp] + s_n[self.env.model.I_icu])
            #     days += 1
            # # S_s_n = s_n[self.env.model.S].sum()
            # # r[1] -= penalty
            # # print(f'additional days: {days} \t penalty {penalty}')
        return s, r, t, info



def create_env(env_type='ODE', discrete_actions=False, simulate_lockdown=True, until=None):
    if env_type == 'ODE':
        env = be_ode()
    else:
        env = be_binomial()
    # set timelimit
    if until is not None:
        env = until(env)
        env = EndPenalty(env)
    if simulate_lockdown:
        env = Lockdown(env)
    if discrete_actions:
        env = discretize_actions(env)
    return env


for env_type in ('ODE', 'Binomial'):
    for discrete_actions in (False, True):
        for simulate_lockdown in (False, True):
            for until in (until_2020_09_01, until_2021_01_01):
                a = 'Discrete' if discrete_actions else 'Continuous'
                l = 'WithLockdown' if simulate_lockdown else ''
                u = 'Until2021' if until == until_2021_01_01 else ''
                # envs
                register(
                    id=f'BECovid{l}{u}{env_type}{a}-v0',
                    entry_point='gym_covid.envs:create_env',
                    kwargs={
                        'env_type': env_type,
                        'discrete_actions': discrete_actions,
                        'simulate_lockdown': simulate_lockdown,
                        'until': until}
                    )
