import numpy as np
import sklearn.metrics
import logging

logger = logging.getLogger()

"""
ROC AUC score
"""
def get_roc_auc_score(y_true, y_score):
    """
    Compute ROC AUC given true labels and score predictions
    :param y_true: [0,1,1,1,0,1,0,0,,1,0,1,0,1,0,1,0,1,...]
    :param y_score: [0.4,0.9,0.5,0.778,0.152,0.123,0.6,...]
    :return: Float representing the area under the ROC curve
    """
    #print("PREDICTIONS (min,max,mean,std): ", (y_score.min(), y_score.max(), y_score.mean(), y_score.std()))
    return sklearn.metrics.roc_auc_score(y_true, y_score, average='micro')


def generate_test_set_nodes(adjacency_matrix, features, ratio, random_state=None):
    """
    Produces train/test sets for link prediction, by sampling nodes
    :param adjacency_matrix:
    :param features:
    :param ratio:
    :return:
    """
    length_data = adjacency_matrix.shape[0]
    np.random.seed(random_state)
    keep_mask = np.random.choice(a=[False, True], size=length_data, p=[1 - ratio, ratio])
    keep_mask_nonzero = keep_mask.nonzero()[0]
    not_keep_nonzero = np.logical_not(keep_mask).nonzero()[0]
    x_test = list()
    y_true = list()
    x_train = list()
    y_true_train = list()
    adjacency_matrix_train = adjacency_matrix[keep_mask][:, keep_mask].copy()
    adjacency_matrix_train.eliminate_zeros()
    non_zer_sets = dict()
    for i, j in zip(*adjacency_matrix.nonzero()):
        non_zer_sets.setdefault(i, set())
        non_zer_sets.setdefault(j, set())
        non_zer_sets[i].add(j)
        non_zer_sets[j].add(i)
    non_zer_sets_train = dict()
    for i, j in zip(*adjacency_matrix_train.nonzero()):
        non_zer_sets_train.setdefault(i, set())
        non_zer_sets_train.setdefault(j, set())
        non_zer_sets_train[i].add(j)
        non_zer_sets_train[j].add(i)

    for k, (i, j, d) in enumerate(
            zip(adjacency_matrix.nonzero()[0], adjacency_matrix.nonzero()[1], adjacency_matrix.data)):
        if not keep_mask[i] and not keep_mask[j]:
            x_test.append((i, j))
            y_true.append(True)
            false_i = i
            false_j = np.random.choice(a=not_keep_nonzero)
            while false_i == false_j or false_j in non_zer_sets[false_i]:
                false_i = np.random.choice(a=keep_mask_nonzero)
                false_j = np.random.choice(a=keep_mask_nonzero)
            x_test.append((false_i, false_j))
            y_true.append(False)
    for k, (i, j, d) in enumerate(
                    zip(adjacency_matrix_train.nonzero()[0], adjacency_matrix_train.nonzero()[1], adjacency_matrix_train.data)):
        x_train.append((i, j))
        y_true_train.append(True)
        false_i = i
        false_j = np.random.randint(0, adjacency_matrix_train.shape[0], dtype=np.int32)
        while false_i == false_j or false_j in non_zer_sets_train[false_i]:
            false_j = np.random.randint(0, adjacency_matrix_train.shape[0], dtype=np.int32)
        x_train.append((false_i, false_j))
        y_true_train.append(False)

    features_train = np.array([features[i] for i in keep_mask_nonzero])
    logger.debug(
        "New link prediction with p={1} test set generated with {0} pairs of nodes "
        "and train set with {2} pairs of nodes".format(
            len(x_test), ratio, len(adjacency_matrix.data)))
    logger.debug("New link prediction with p={1} test set generated with {0} nodes"
                " and train set with {2} nodes".format(
        (keep_mask == False).sum(), ratio, (keep_mask == True).sum()))
    y_true = np.array(y_true, dtype=np.bool)
    y_true_train = np.array(y_true_train, dtype=np.bool)
    x_test = np.array(x_test, dtype=np.int)
    x_train = np.array(x_train, dtype=np.int)
    return adjacency_matrix_train, features_train, x_test, y_true, x_train, y_true_train


def test(model, x, y, features):
    y_score = list()
    for k, (i, j) in enumerate(x):
        y_score.append(model.predict_new(features[i], features[j]))
    return get_roc_auc_score(y, np.nan_to_num(np.array(y_score, dtype=np.float)))


def evaluate(model, adjacency_matrix, features, proportions, n_trials = 1, random_state=None):
    scores = {
        'proportion': proportions,
        'micro': np.zeros(len(proportions)),
        'std': np.zeros(len(proportions)),
        'micro_train': np.zeros(len(proportions))
    }
    for i, p in enumerate(proportions):
        std = list()
        for _ in range(n_trials):
            model.__init__()
            adjacency_matrix_train, features_train, x_test, y_true, x_train, y_true_train = \
                generate_test_set_nodes(
                    adjacency_matrix,
                    features,
                    p,
                    random_state
                )

            model.fit(adjacency_matrix_train, features_train)

            subsampling = np.arange(len(x_test))
            np.random.shuffle(subsampling)
            subsampling = subsampling[0:1000]

            sc = test(
                model,
                x_test[subsampling],
                y_true[subsampling],
                features
            )

            scores["micro"][i] += sc/n_trials

            std.append(sc)

            """
            subsampling = np.arange(len(x_train))
            np.random.shuffle(subsampling)
            subsampling = subsampling[0:1000]

            scores["micro_train"][i] += test(
                model,
                x_train[subsampling],
                y_true_train[subsampling],
                features_train
            )/n_trials
            """

        scores["std"][i] = np.array(std).std()

    return scores