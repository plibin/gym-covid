import sys
import os
sys.path.append(os.getcwd())
import matplotlib.pyplot as plt

def plot_simulation(states):
    fig, axs = plt.subplots(2, 1)
    for ag in range(2):
        ax = axs[ag]
        s, i, r = states[:, ag*3+0], states[:, ag*3+1], states[:, ag*3+2]

        ax.plot(s, c='b', label='s')
        ax.plot(i, c='r', label='i')
        ax.plot(r, c='g', label='r')
        ax.set_xlabel('week')
        ax.set_ylabel('pop')
    plt.show()


if __name__ == '__main__':
    import gym
    import envs
    from gym.wrappers import TimeLimit
    import numpy as np
    
    env = gym.make('EpiODEContinuous-v0')
    env = TimeLimit(env, 48)
    states = []
    s = env.reset()
    d = False
    states.append(s)
    while not d:
        a = env.action_space.sample()
        s, r, d, _ = env.step(a)
        print(s, r)
        states.append(s)
    
    states = np.array(states)
    plot_simulation(states)