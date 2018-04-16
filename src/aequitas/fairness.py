import logging

import pandas as pd

logging.getLogger(__name__)

# Authors: Pedro Saleiro <saleiro@uchicago.edu>
#          Rayid Ghani
#
# License: Copyright \xa9 2018. The University of Chicago. All Rights Reserved.


class Fairness(object):
    """
    """
    def __init__(self, fair_eval=None, tau=None, fair_measures_depend=None, type_parity_depend=None,
                 high_level_fairness_depend=None):
        """

        :param fair_eval: a lambda function that is used to assess fairness (e.g. 80% rule)
        :param tau: the threshold for fair/unfair
        :param fair_measures: a dictionary containing fairness measures as keys and the
        corresponding input bias metric as values
        """
        if not fair_eval:
            self.fair_eval = lambda tau: lambda x: True if tau <= x <= 1 / tau else False
        else:
            self.fair_eval = fair_eval
        # tau is the fairness_threshold and should be a real ]0.0 and 1.0]
        if not tau:
            self.tau = 0.8
        else:
            self.tau = tau

        self.high_level_pair_eval = lambda col1, col2: lambda x: True if (x[col1] is True and x[col2] is
                                                                          True) else False
        self.high_level_single_eval = lambda col: lambda x: True if x[col] is True else False

        # the fair_measures_depend define the bias metrics that serve as input to the fairness evaluation and respective
        # fairness measure. basically these are the fairness measures supported by the current version of aequitas.

        if not fair_measures_depend:
            self.fair_measures_depend = {'Statistical Parity': 'ppr_disparity',
                                         'Impact Parity': 'pprev_disparity',
                                         'FDR Parity': 'fdr_disparity',
                                         'FPR Parity': 'fpr_disparity',
                                         'FOR Parity': 'for_disparity',
                                         'FNR Parity': 'fnr_disparity'}
        else:
            self.fair_measures_depend = fair_measures_depend
        # the self.fair_measures represents the list of fairness_measures to be calculated by default
        self.fair_measures_supported = self.fair_measures_depend.keys()

        if not type_parity_depend:
            self.type_parity_depend = {'TypeI Parity': ['FDR Parity', 'FPR Parity'],
                                       'TypeII Parity': ['FOR Parity', 'FNR Parity']}
        else:
            self.type_parity_depend = type_parity_depend

        # high level fairness_depend define which input fairness measures are used to calculate the high level ones
        if not high_level_fairness_depend:
            self.high_level_fairness_depend = {
                'Unsupervised Fairness': ['Statistical Parity', 'Impact Parity'],
                'Supervised Fairness': ['TypeI Parity', 'TypeII Parity']}
        else:
            self.high_level_fairness_depend = high_level_fairness_depend

    def get_group_value_fairness(self, bias_df, tau=None, fair_measures_requested=None):
        """
            Calculates the fairness measures defined in the fair_measures dictionary and adds
            them as columns to the input bias_df

        :param bias_df: the output dataframe from the bias/disparities calculations
        :param fair_eval: (optional) see __init__()
        :param tau: (optional) see __init__()
        :param fair_measures: (optional) see __init__()
        :return: the input bias_df dataframe with additional columns for each of the fairness
        measures defined in the fair_measures dictionary
        """
        logging.info('get_group_value_fairness...')
        if not tau:
            tau = self.tau
        if not fair_measures_requested:
            fair_measures_requested = self.fair_measures_supported

        for fair, input in self.fair_measures_depend.items():
            if fair in fair_measures_requested:
                bias_df[fair] = bias_df[input].apply(self.fair_eval(tau))
        for fair, input in self.type_parity_depend.items():
            if input[0] in bias_df.columns:
                if input[1] in bias_df.columns:
                    bias_df[fair] = bias_df.apply(self.high_level_pair_eval(input[0], input[1]), axis=1)
                else:
                    bias_df[fair] = bias_df.apply(self.high_level_single_eval(input[0]), axis=1)
            elif input[1] in bias_df.columns:
                bias_df[fair] = bias_df.apply(self.high_level_single_eval(input[1]), axis=1)
            else:
                logging.info('get_group_value_fairness: No Parity measure input found on bias_df')
        for fair, input in self.high_level_fairness_depend.items():
            if input[0] in bias_df.columns:
                if input[1] in bias_df.columns:
                    bias_df[fair] = bias_df.apply(self.high_level_pair_eval(input[0], input[1]), axis=1)
                else:
                    bias_df[fair] = bias_df.apply(self.high_level_single_eval(input[0]), axis=1)
            elif input[1] in bias_df.columns:
                bias_df[fair] = bias_df.apply(self.high_level_single_eval(input[1]), axis=1)
        if 'Unsupervised Fairness' not in bias_df.columns and 'Supervised Fairness' not in bias_df.columns:
            logging.info('get_group_value_fairness: No high level measure input found on bias_df' + input[1])
        return bias_df

    def get_group_attribute_fairness(self, group_value_df, fair_measures_requested=None):
        """

        :param group_value_df: the output dataframe of the get_group_value_fairness()
        :return: a new dataframe at the group_attribute level (no group_values) with fairness
        measures at the group_attribute level. Checks for the min (False) across the groups
        defined by the group_attribute. IF the minimum is False then all group_attribute is false
        for the given fairness measure.
        """
        logging.info('get_group_attribute_fairness')
        if not fair_measures_requested:
            fair_measures_requested = self.fair_measures_supported
        group_attribute_df = pd.DataFrame()
        key_columns = ['model_id', 'score_threshold', 'attribute_name']
        groupby_variable = group_value_df.groupby(key_columns)
        init = 0
        for key in fair_measures_requested:
            df_min_idx = group_value_df.loc[groupby_variable[key].idxmin()]
            if init == 0:
                group_attribute_df[key_columns + [key]] = df_min_idx[key_columns + [key]]
            else:
                group_attribute_df = group_attribute_df.merge(df_min_idx[key_columns + [key]],
                                                              on=key_columns)
            init = 1
        # todo throw exception instead of exiting
        if group_attribute_df.empty:
            logging.error('get_group_attribute_fairness: no fairness measures requested found on input group_value_df columns')
            exit(1)
        for key in self.type_parity_depend:
            if key in group_value_df.columns:
                df_min_idx = group_value_df.loc[groupby_variable[key].idxmin()]
                group_attribute_df = group_attribute_df.merge(df_min_idx[key_columns + [key]],
                                                              on=key_columns)
        for key in self.high_level_fairness_depend:
            if key in group_value_df.columns:
                df_min_idx = group_value_df.loc[groupby_variable[key].idxmin()]
                group_attribute_df = group_attribute_df.merge(df_min_idx[key_columns + [key]],
                                                              on=key_columns)

        return group_attribute_df

    def get_overall_fairness(self, group_attribute_df):
        """
            Calculates overall fairness regardless of the group_attributes. It searches for
            unfairness across group_attributes and outputs fairness if all group_attributes are fair

        :param group_attribute_df: the output df of the get_group_attributes_fairness
        :return: dictionary with overall unsupervised/supervised fairness and fairness in general
        """
        overall_fairness = {}
        if 'Unsupervised Fairness' in group_attribute_df.columns:
            overall_fairness['Unsupervised Fairness'] = False if \
                group_attribute_df['Unsupervised Fairness'].min() == False else True

        if 'Supervised Fairness' in group_attribute_df.columns:
            overall_fairness['Supervised Fairness'] = False if group_attribute_df['Supervised Fairness'].min() == False else True

        fair_vals = [val for key, val in overall_fairness.items()]
        if False in fair_vals:
            overall_fairness['Overall Fairness'] = False
        elif True in fair_vals:
            overall_fairness['Overall Fairness'] = True
        else:
            overall_fairness['Overall Fairness'] = 'Unknown!'
        return overall_fairness

