import argparse
import glob
import os
import random
import re
from collections import OrderedDict

import numpy as np
import pandas as pd
import torch
from dataset import data_loader
from eval.post_process import *
from neural_methods.model.DeepPhys import DeepPhys
from neural_methods.model.PhysNet import PhysNet_padding_Encoder_Decoder_MAX
from neural_methods.model.TS_CAN import TSCAN
from torch.utils.data import DataLoader


def read_label(dataset):
    df = pd.read_csv("label/{0}_Comparison.csv".format(dataset))
    out_dict = df.to_dict(orient='index')
    out_dict = {str(value['VideoID']): value for key, value in out_dict.items()}
    return out_dict


def read_hr_label(feed_dict, index):
    # For UBFC only
    if index[:7] == 'subject':
        index = index[7:]
    video_dict = feed_dict[index]
    if video_dict['Preferred'] == 'Peak Detection':
        hr = video_dict['Peak Detection']
    elif video_dict['Preferred'] == 'FFT':
        hr = video_dict['FFT']
    else:
        hr = video_dict['Peak Detection']
    return index, hr


def reform_data_from_dict(data):
    # print('before:', (data.items()))
    sort_data = sorted(data.items(), key=lambda x: x[0])
    #debug test
    # print('after:', sort_data)
    sort_data = [i[1] for i in sort_data]
    sort_data = torch.cat(sort_data, dim=0)
    return np.reshape(sort_data.cpu(), (-1))


def calculate_metrics(predictions, labels, config):
    predict_hr_fft_all = list()
    gt_hr_fft_all = list()
    predict_hr_peak_all = list()
    gt_hr_peak_all = list()
    SNR_all = list()
    for index in predictions.keys():
        prediction = reform_data_from_dict(predictions[index])
        label = reform_data_from_dict(labels[index])

        if config.TRAIN.DATA.PREPROCESS.LABEL_TYPE == "Standardized" or \
                config.TRAIN.DATA.PREPROCESS.LABEL_TYPE == "Raw" or \
                config.TRAIN.DATA.PREPROCESS.LABEL_TYPE == "PhysNormalized":
            diff_flag_test = False
        elif config.TRAIN.DATA.PREPROCESS.LABEL_TYPE == "Normalized":
            diff_flag_test = True
        else:
            raise ValueError("Not supported label type in testing!")
        gt_hr_fft, pred_hr_fft, SNR = calculate_metric_per_video(
            prediction, label, diff_flag=diff_flag_test, fs=config.TEST.DATA.FS)
        gt_hr_peak, pred_hr_peak = calculate_metric_peak_per_video(
            prediction, label, diff_flag=diff_flag_test, fs=config.TEST.DATA.FS)
        gt_hr_fft_all.append(gt_hr_fft)
        #debug test
        # print(gt_hr_fft,pred_hr_fft)
        predict_hr_fft_all.append(pred_hr_fft)
        predict_hr_peak_all.append(pred_hr_peak)
        gt_hr_peak_all.append(gt_hr_peak)
        SNR_all.append(SNR)
    predict_hr_peak_all = np.array(predict_hr_peak_all)
    predict_hr_fft_all = np.array(predict_hr_fft_all)
    gt_hr_peak_all = np.array(gt_hr_peak_all)
    gt_hr_fft_all = np.array(gt_hr_fft_all)
    SNR_all = np.array(SNR_all)
    for metric in config.TEST.METRICS:
        if metric == "MAE":
            if config.INFERENCE.EVALUATION_METHOD == "FFT":
                MAE_FFT = np.mean(np.abs(predict_hr_fft_all - gt_hr_fft_all))
                print("FFT MAE (FFT Label):{0}".format(MAE_FFT))
            elif config.INFERENCE.EVALUATION_METHOD == "peak detection":
                MAE_PEAK = np.mean(np.abs(predict_hr_peak_all - gt_hr_peak_all))
                print("Peak MAE (Peak Label):{0}".format(MAE_PEAK))
            else:
                raise ValueError("Your evaluation method is not supported yet! Support FFT and peak detection now ")

        elif metric == "RMSE":
            if config.INFERENCE.EVALUATION_METHOD == "FFT":
                RMSE_FFT = np.sqrt(np.mean(np.square(predict_hr_fft_all - gt_hr_fft_all)))
                print("FFT RMSE (FFT Label):{0}".format(RMSE_FFT))
            elif config.INFERENCE.EVALUATION_METHOD == "peak detection":
                RMSE_PEAK = np.sqrt(np.mean(np.square(predict_hr_peak_all - gt_hr_peak_all)))
                print("PEAK RMSE (Peak Label):{0}".format(RMSE_PEAK))
            else:
                raise ValueError("Your evaluation method is not supported yet! Support FFT and peak detection now ")

        elif metric == "MAPE":
            if config.INFERENCE.EVALUATION_METHOD == "FFT":
                MAPE_FFT = np.mean(np.abs((predict_hr_fft_all - gt_hr_fft_all) / gt_hr_fft_all)) * 100
                print("FFT MAPE (FFT Label):{0}".format(MAPE_FFT))
            elif config.INFERENCE.EVALUATION_METHOD == "peak detection":
                MAPE_PEAK = np.mean(np.abs((predict_hr_peak_all - gt_hr_peak_all) / gt_hr_peak_all)) * 100
                print("PEAK MAPE (Peak Label):{0}".format(MAPE_PEAK))
            else:
                raise ValueError("Your evaluation method is not supported yet! Support FFT and peak detection now ")

        elif metric == "Pearson":
            if config.INFERENCE.EVALUATION_METHOD == "FFT":
                Pearson_FFT = np.corrcoef(predict_hr_fft_all, gt_hr_fft_all)
                print("FFT Pearson (FFT Label):{0}".format(Pearson_FFT[0][1]))
            elif config.INFERENCE.EVALUATION_METHOD == "peak detection":
                Pearson_PEAK = np.corrcoef(predict_hr_peak_all, gt_hr_peak_all)
                print("PEAK Pearson  (Peak Label):{0}".format(Pearson_PEAK[0][1]))
            else:
                raise ValueError("Your evaluation method is not supported yet! Support FFT and peak detection now ")

        ### added
        elif metric == 'SNR':
            if config.INFERENCE.EVALUATION_METHOD == "FFT" or "peak detection":
                SNR_FFT = np.nanmean(SNR_all)
                print("FFT SNR(FFT Label):{0}".format(SNR_FFT))
            else:
                raise ValueError("Your evaluation method is not supported yet! Support FFT and peak detection now ")

        else:
            raise ValueError("Wrong Test Metric Type")

    return MAE_FFT, RMSE_FFT, MAPE_FFT, Pearson_FFT[0][1], SNR_FFT