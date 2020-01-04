import numpy as np
import sklearn.preprocessing
from multiprocessing.pool import ThreadPool
import logging

logger = logging.getLogger()


class RandomChoice(object):
    """
    A class to generate random choices given a probability distribution p.
    Use the same code as numpy.random.random_choice, but the initilization is made only once.
    This is useful when calling multiple times and when it is impossible to guess in advance 
    the number of calls (stochastic process).
    p doesn't have to be normalized (sum=1).  
    """

    def __init__(self, p):
        p /= p.sum()
        self.cdf = p.cumsum()
        self.cdf /= self.cdf[-1]

    def get(self):
        uniform_samples = np.random.random_sample(1)
        idx = self.cdf.searchsorted(uniform_samples, side='right').astype(np.int32)
        return idx[0]


class MultipleRandomChoice(object):
    """
    A class to generate random choices given multiple probabilities distributions extracted from a sparse representation mat.
    For each row, the probability distribution is extracted. Then calling __getitem__(i) draw a sample given the distribution
    of mat[i].
    By default, if a row i has no entry, the sample i will be returned.
    """

    def __init__(self, mat):
        mat.eliminate_zeros()
        self.nodes_number = mat.shape[0]
        transition_probs = sklearn.preprocessing.normalize(mat, axis=1, norm='l1', copy=False)
        nonzero = transition_probs.nonzero()
        data = transition_probs.data
        K = len(data)
        choices = list()
        probs = list()
        k = 0
        for i in range(self.nodes_number):
            choices.append(list())
            probs.append(list())
            if k >= K:  #  if we're done looping on the data, we fill the remaining nodes probs
                choices[i] = np.array([i], dtype=np.int32)
                probs[i] = np.array([1], dtype=np.float32)
                continue
            elif nonzero[0][k] > i:  #  if the current node has no transition
                choices[i] = [i]
                probs[i] = np.array([1], dtype=np.float32)
            else:
                while k < K and nonzero[0][k] == i:  #  loop over currrent node transitions indices/probabilities
                    choices[i].append(nonzero[1][k])
                    probs[i].append(data[k])
                    k += 1
            choices[i] = np.array(choices[i], dtype=np.int32)
            probs[i] = np.array(probs[i], dtype=np.float32)
        self.choices = choices
        self.rc = list()
        for i in range(self.nodes_number):
            self.rc.append(RandomChoice(probs[i]))

    def __getitem__(self, arg):
        return self.choices[arg][self.rc[arg].get()]


def generate_batches(X, number_negative, number_iterations, batch_size):
    """
    One possible generator, given a simialrity matrix X, a number of negative samples to draw, an absolute number of iterations, and a batch size.
    For each iteration, draws uniformly batch_size postive samples and number_negative*batch_size negative samples.
    Positive samples are generated by drawing the context with the real distribution in X
    Negative samples are generated by drawing uniformly samples.
    Positive pairs are associated with x=-1
    Nagative pairs are associated with x=1
    Return: list of (u,v,x) of length batch_size * (1 + number_negative)
    Example: batch_size = 1, number_negative = 3  => [ (7,12,0), (7,2,-1), (7,7,1), (7,2,1) ]
    """
    number_nodes = X.shape[0]
    random_choice = MultipleRandomChoice(X)
    available_nodes = np.arange(number_nodes, dtype=np.int32)
    probs = np.squeeze(np.asarray(X.sum(axis=1) / X.sum()))
    for i in range(number_iterations):
        drawn = np.random.randint(0, number_nodes, batch_size, dtype=np.int32)  # draws uniformly some nodes
        # drawn = np.random.choice(available_nodes, p=probs, size=batch_size)      # draws nodes from empirical distribution of co-occurrences (edges)
        batch_u = np.tile(drawn, number_negative + 1)
        batch_v = np.zeros(batch_size, dtype=np.int32)
        for j in range(batch_size):
            batch_v[j] = random_choice[batch_u[j]]
        batch_v = np.hstack((batch_v, np.random.randint(0, number_nodes, batch_size * number_negative, dtype=np.int32)))
        batch_x = np.hstack(
            (np.ones(batch_size, dtype=np.float32), -np.ones(batch_size * number_negative, dtype=np.float32)))
        shuind = np.arange(len(batch_x))
        np.random.shuffle(shuind)
        try:
            yield batch_u[shuind], batch_v[shuind], batch_x[shuind]
        except StopIteration:
            return


def async_batches(X, number_negative, number_iterations, batch_size):
    """
    A wrapper that computes next batch asynchronously before next call.
    """
    it = generate_batches(X, number_negative, number_iterations, batch_size)
    try:
        current_batch = next(it)
    except StopIteration:
        return
    pool = ThreadPool(processes=1)
    while current_batch:
        try:
            async_result = pool.apply_async(it.__next__)
            yield current_batch
            current_batch = async_result.get()
        except StopIteration:
            return

"""
Example of use

for i, (u,v,x) in enumerate(data_generator.async_batches(X, number_negative, number_iterations, batch_size)):
    DO SOMETHING WITH IT
"""
