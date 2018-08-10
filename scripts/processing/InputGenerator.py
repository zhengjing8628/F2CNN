import csv
import glob
import time
from configparser import ConfigParser
from os.path import join, isdir

import numpy
from matplotlib.colors import LogNorm

from scripts.processing.OrganiseFiles import completeSplit


def GetListOfEnvelopeFilesAndTimepoints(labelFilename):
    """
    Takes a label csv file, and generates a list of [['TEST' or 'TRAIN', filename], [timepoints]] arrays
    :param labelFilename: csv label file
    :return: the described array
    """
    output = dict()
    with open(labelFilename, 'r') as labelFile:
        csvLabelReader = csv.reader(labelFile)
        for i, (testOrTrain, region, speaker, sentence, phoneme, timepoint, slope, pvalue, sign) in enumerate(
                csvLabelReader):
            file = join(testOrTrain, '.'.join((region, speaker, sentence, 'ENV1.npy')))
            if file not in output.keys():
                output[file] = [int(timepoint)]
            else:
                output[file].append(int(timepoint))
    return output


def GenerateInputData(LPF=False, CUTOFF=100):
    TotalTime = time.time()

    # The csv label data is inside regular trainingData directory
    if not isdir(join("trainingData")):
        print("LABEL GENERATION SHOULD BE DONE PRIOR TO INPUT...")
        exit(-1)
    csvFilename = join("trainingData", "label_data.csv")

    filesAndTimepointsDict = GetListOfEnvelopeFilesAndTimepoints(csvFilename)

    print("\n###############################\nGenerating Input Data from files with '{}'.".format(csvFilename))
    if LPF:
        print("Using Low Pass Filtering with a cutoff at {}Hz".format(CUTOFF))
    else:
        print("Not using Low Pass Filtering")

    if not filesAndTimepointsDict:
        print("NO ENV1.npy FILES FOUND")
        exit(-1)
    files=filesAndTimepointsDict.keys()
    files=sorted(files)
    totalTimePoints = sum([len(data) for data in filesAndTimepointsDict.values()])
    print(len(filesAndTimepointsDict.keys()), "files found along with their",
          totalTimePoints, "entry timepoints.")
    # #### READING CONFIG FILE
    config = ConfigParser()
    config.read('F2CNN.conf')
    radius = config.getint('CNN', 'RADIUS')
    sampPeriod = config.getint('CNN', 'sampperiod')
    framerate = config.getint('FILTERBANK', 'framerate')
    nchannels = config.getint('FILTERBANK', 'nchannels')
    dotsperinput = radius * 2 + 1

    inputData = numpy.zeros((totalTimePoints, dotsperinput, nchannels))
    print("Output shape:", inputData.shape)
    STEP = int(framerate*sampPeriod/1000000)
    currentEntry = 0
    for currentFileIndex, file in enumerate(files):
        timepoints=filesAndTimepointsDict[file]
        file = join('resources', 'f2cnn', file)
        print("Reading:\t\t{}".format(file))
        envelopes = numpy.load(file)
        i=0
        for i, center in enumerate(timepoints):
            entryMatrix = numpy.zeros((dotsperinput,nchannels))  # All the values for one entry(11 timepoints centered around center) : 11x128 matrix
            for j, index in enumerate([center + STEP * (k - 5) for k in range(dotsperinput)]):
                valueArray = numpy.array([channel[index] for channel in envelopes])  # All the values of env at the steps' timepoint
                entryMatrix[j]=valueArray
            inputData[currentEntry+i]=entryMatrix
        currentEntry+=i+1
        print("\t\t{:<50} done !  {}/{} Files".format(file,currentFileIndex+1, len(filesAndTimepointsDict.keys())))
    inputData = numpy.array(inputData, dtype=numpy.float32)
    print('Generated Input Matrix of shape {}.'.format(inputData.shape))

    savePath = 'trainingData/input_data_LPF{}.npy'.format(CUTOFF) if LPF else 'trainingData/input_data.npy'

    print("Saving {}...".format(savePath))
    numpy.save(savePath, inputData)
    print('                Total time:', time.time() - TotalTime)
    print('')