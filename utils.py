import torch
import numpy as np
from lifelines.statistics import logrank_test
from lifelines.utils import concordance_index


def hazard2grade(survival, p):
    """
    To convert month prediction to year
    survival: the prediction of month,
           p: the threshold, e.g., 60 denotes 60 months equal to 5 years
    """
    label = []
    for os_time in survival:
        if os_time < p:
            label.append(0)
        else:
            label.append(1)
    return label


def p(n):
    def percentile_(x):
        return np.percentile(x, n)

    percentile_.__name__ = 'p%s' % n
    return percentile_


def R_set(x):
    """
    Layered summation

     [1   0   0]    [a   b   c]   [a     b     c    ]
     [1   1   0] ·  [c   a   b] = [a+c   b+a   c+b  ]
     [1   1   1]    [b   c   a]   [a+c+b b+a+c c+b+a]
    """
    n_sample = x.size(0)
    matrix_ones = torch.ones(n_sample, n_sample)
    indicator_matrix = torch.tril(matrix_ones)  
    return indicator_matrix


def regularize_weights(model, reg_type=None):
    l1_reg = None
    for W in model.parameters():
        if l1_reg is None:
            l1_reg = torch.abs(W).sum()
        else:
            l1_reg = l1_reg + torch.abs(W).sum()  # torch.abs(W).sum() is equivalent to W.norm(1)
    return l1_reg


def cox_log_rank(hazardsdata, labels, survtime_all):
    median = np.median(hazardsdata)                                     # The middle value of all data that is sorted
    hazards_dichotomize = np.zeros([len(hazardsdata)], dtype=int)
    hazards_dichotomize[hazardsdata > median] = 1                       # High risk
    idx = hazards_dichotomize == 0                                      # Indexes of low risk samples
    T1 = survtime_all[idx]              # Durations of low risk samples
    T2 = survtime_all[~idx]             # Durations of high risk samples
    E1 = labels[idx]
    E2 = labels[~idx]
    results = logrank_test(T1, T2, event_observed_A=E1, event_observed_B=E2)
    pvalue_pred = results.p_value
    return (pvalue_pred)


def accuracy_cox(hazardsdata, labels):
    median = np.median(hazardsdata)
    hazards_dichotomize = np.zeros([len(hazardsdata)], dtype=int)
    hazards_dichotomize[hazardsdata > median] = 1
    correct = np.sum(hazards_dichotomize == labels)
    return correct / len(labels)


def CIndex_lifeline(hazards, labels, survtime_all):
    return concordance_index(survtime_all, -hazards, labels)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def CoxLoss(
        survtime,       # of shape (b_s, 1)
        censor,         # of shape (b_s, 1)
        hazard_pred,    # of shape (b_s, 1)
        device):

    n_observed = censor.sum(0) + 1  # censor.sum(0): the num of event samples
    ytime_indicator = R_set(survtime)  
    ytime_indicator = torch.FloatTensor(ytime_indicator).to(device)
    risk_set_sum = ytime_indicator.mm(torch.exp(hazard_pred))   # Accumulated risk of batch samples, of shape (b_s, 1)
    diff = hazard_pred - torch.log(risk_set_sum)
    sum_diff_in_observed = torch.transpose(diff, 0, 1).mm(censor.unsqueeze(1))  # (1, b_s)·(b_s, 1, 1) = (1, 1, 1)
    cost = (- (sum_diff_in_observed / n_observed)).reshape((-1,))

    return cost
