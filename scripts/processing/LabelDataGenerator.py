"""

This file generates labelling data for the CNN, as a .CSV file of columns:
TESTorTRAIN,Region(DR1-8),SpeakerID,SentenceID,framepoint,slope,p-valueOfSlope,slopeSign(+-1)
Requires a prior execution of the OrganiseFiles.py, GammatoneFiltering.py, EnvelopeExtraction.py scripts' main functions

"""
from configparser import ConfigParser

import numpy
import csv
import glob
import time
import wave
from os import mkdir
from scipy.stats import pearsonr
from os.path import join, split, splitext, isdir

from scripts.processing.GammatoneFiltering import ConvertWavFile
from scripts.processing.OrganiseFiles import completeSplit
from .FBFileReader import GetF2Frequencies, GetF2FrequenciesAround
from .PHNFileReader import GetPhonemeAt, SILENTS


def GetLabelsFromFile(filename):
    testOrTrain, filename = split(filename)
    testOrTrain = split(testOrTrain)[1]
    region, speaker, sentence = splitext(filename)[0].split('.')
    print(testOrTrain, region, speaker, sentence)


def GenerateLabelData(testMode):
    TotalTime = time.time()

    # #### READING CONFIG FILE
    config = ConfigParser()
    config.read('F2CNN.conf')
    radius = config.getint('CNN', 'RADIUS')
    RISK = config.getfloat('CNN', 'RISK')
    sampPeriod = config.getint('CNN', 'sampperiod')
    framerate = config.getint('FILTERBANK', 'framerate')
    dotsperinput = radius * 2 + 1
    ustos=1.0/1000000
    if testMode:
        # Test files
        filenames = glob.glob(join("testFiles", "*.WAV"))
    else:
        # Get all the files under resources
        filenames = glob.glob(join("resources", "f2cnn", "*", "*.WAV"))

    print("\n###############################\nGenerating Label Data from files in '{}'.".format(
        split(split(filenames[0])[0])[0]))

    # Alphanumeric order
    filenames = sorted(filenames)

    if not filenames:
        print("NO FILES FOUND")
        exit(-1)

    print(len(filenames), "files found")

    vowelCounter = 0
    csvLines = []

    # Get the data into a list of lists for the CSV
    for i, file in enumerate(filenames):
        print(i, "Reading:\t{}".format(file))
        # Load the F2 values of the file
        F2Array, _ = GetF2Frequencies(splitext(file)[0] + '.FB')

        # Get number of points
        try:
            wavFile = wave.open(file, 'r')
        except wave.Error:
            print("Converting file to correct format...")
            ConvertWavFile(file)
            wavFile = wave.open(file, 'r')
        framerate = wavFile.getframerate()
        nf=wavFile.getnframes()
        nb = int(nf/(framerate*sampPeriod*ustos)-dotsperinput-1)
        wavFile.close()

        # Get the information about the person
        region, speaker, sentence, _ = split(file)[1].split(".")
        testOrTrain = split(split(file)[0])[1]

        # Discretization of the values for each entry required
        STEP = int(framerate * sampPeriod*ustos)
        START = int(STEP * radius)
        steps = [START+k*STEP for k in range(nb)]
        for step in steps:
            phoneme = GetPhonemeAt(splitext(file)[0] + '.PHN', step)
            if phoneme in SILENTS:
                continue
            if not phoneme:
                break
            entry = [testOrTrain, region, speaker, sentence, phoneme, step]
            F2Values = numpy.array(GetF2FrequenciesAround(F2Array, step, radius))

            # Least Squares Method for linear regression of the F2 values
            x = numpy.array([step+(k-5)*STEP for k in range(dotsperinput)])
            A = numpy.vstack([x, numpy.ones(len(x))]).T
            [a, b], _, _, _ = numpy.linalg.lstsq(A, F2Values, rcond=None)
            # Pearson Correlation Coefficient r and p-value p using scipy.stats.pearsonr
            r, p = pearsonr(F2Values, a * x + b)
            # We round them up at 5 digits after the comma
            entry.append(round(a, 5))
            entry.append(round(p, 5))
            # The line to be added to the CSV file, only if the direction of the formant is clear enough (% risk)
            if p < RISK:
                vowelCounter += 1
                entry.append(1 if a > 0 else 0)
                csvLines.append(entry)
        print("\t\t{:<50} done !".format(file))

    # Saving into a file
    if testMode:
        if not isdir(join("testFiles", "trainingData")):
            mkdir(join("testFiles", "trainingData"))
        filePath = join("testFiles", "trainingData", "label_data.csv")
    else:
        filePath = join("trainingData", "label_data.csv")
    with open(filePath, "w") as outputFile:
        writer = csv.writer(outputFile)
        for line in csvLines:
            writer.writerow(line)
    print("Generated Label Data CSV of", vowelCounter, "lines.")
    print('                Total time:', time.time() - TotalTime)
    print('')

"""

TRAIN/DR3.MDTB0.SX210.ENV1.npy
TRAIN/DR4.MTRC0.SI1623.ENV1.npy

"""