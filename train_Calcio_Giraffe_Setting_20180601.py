from UBCNN import *
from UBMetrics import *
import keras
from keras import backend as k
from keras.datasets import cifar10
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation, Flatten
from keras.layers import Conv2D, MaxPooling2D
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve
from keras.callbacks import ModelCheckpoint, Callback
from sklearn.model_selection import KFold
from scipy import ndimage
import sys
import csv
import os

#Network Metadata
prefix = str(sys.argv[1])

np.random.seed(42)

reader = ImageReader()

save_dir = os.path.join(os.getcwd(), 'saved_models')

name_pullbacks_x = 'PULLBACKS_X_GIRAFFE.csv'
name_pullbacks_y = 'PULLBACKS_Y_GIRAFFE.csv'
name_pullbacks_names = 'PULLBACKS_NAMES_GIRAFFE.csv'
allress = []
print('Readed Started..')

#Reader, size of reader defined here
X,Y,start_indices,end_indices = reader.read_pullbacks_from_CSV(names=name_pullbacks_names,file_x=name_pullbacks_x,file_y=name_pullbacks_y,dim=128)
print('Read Complete..')


X = X/255.0
#Calcium Label Index
Y = Y[:,2]

N_pullbacks = len(start_indices)

print(N_pullbacks)

indices_pullbacks = range(N_pullbacks)

N_folds = 10
kf = KFold(n_splits=N_folds, shuffle=True, random_state=42)

tr_epochs = 100

current_fold = 0

ts_accs = np.zeros((10,tr_epochs))
tr_accs = np.zeros((10,tr_epochs))
precisions = np.zeros((10,tr_epochs))
recalls = np.zeros((10,tr_epochs))

counter = 0

#'3-BN-32-04'
basename ='UB_Calcium_' + prefix
name_performance_csv = '_UB_Calcium_PreRec.csv'
model_name = prefix +'UBCNN_Calcio_trained_model.h5'
name_performance_csv = prefix + name_performance_csv

#Split Data for Cross-Fold
for train_pullbacks, test_pullbacks in kf.split(indices_pullbacks):
	frame_tr_indices_cnn = None
	frame_tr_indices_rnn = None
	frame_test_indices = None

	nseq_train = len(train_pullbacks)
	nseq_train_cnn = int(np.floor(nseq_train/2.0))
	nseq_train_rnn = nseq_train-nseq_train_cnn

	train_pullbacks_cnn = train_pullbacks[:nseq_train_cnn]
	train_pullbacks_rnn = train_pullbacks[nseq_train_cnn:]

	for idx in train_pullbacks_cnn:
		new_indices = [int(i) for i in range(start_indices[idx],end_indices[idx]+1)]
		if frame_tr_indices_cnn is None:
			frame_tr_indices_cnn = new_indices
		else:
			frame_tr_indices_cnn = np.r_[frame_tr_indices_cnn,new_indices]

	for idx in train_pullbacks_rnn:
		new_indices = [int(i) for i in range(start_indices[idx],end_indices[idx]+1)]
		if frame_tr_indices_rnn is None:
			frame_tr_indices_rnn = new_indices
		else:
			frame_tr_indices_rnn = np.r_[frame_tr_indices_rnn,new_indices]

	for idx in test_pullbacks:
		new_indices = [int(i) for i in range(start_indices[idx],end_indices[idx]+1)]
		if frame_test_indices is None:
			frame_test_indices = new_indices
		else:
			frame_test_indices = np.r_[frame_test_indices,new_indices]

	X_train_cnn = X[frame_tr_indices_cnn,:]
	y_train_cnn = Y[frame_tr_indices_cnn]
	X_test = X[frame_test_indices,:]
	y_test = Y[frame_test_indices]

	#Network Definition
	net = MauNet_Calcio_3L_BN()
	smetrics = SingleLabelMonitor()
	net.compile_model(input_shape=(128,128),n_target_feat=1,dropout=0.4,nfilters=32)

	results_file = basename +'%dEp_Fold%d_Of_%d.results'%(tr_epochs,current_fold,N_folds)
	filename = basename +'_%dEp_Fold%d_Of_%d.model'%(tr_epochs,current_fold,N_folds)

	print 'Experiment: ' + filename + ' Fold: ' + str(current_fold)

	net_name = 'SingleNet_Calcio_30CLEAN_UNION_FOLD%d'%current_fold
	target_vars = ['calcio']

	#Training method definition train_model for normal training and train_model_DA with real-time data augmentation
	history = net.train_model_DA(X_train_cnn, y_train_cnn, X_val=X_test, y_val=y_test, batch_size=8, n_epochs=tr_epochs,save_name=filename,callbacks=[smetrics])

	history_tr_acc = history.history['acc']
	history_val_acc = history.history['val_acc']

	shape_X_train = X_train_cnn.shape
	shape_Y_train = y_train_cnn.shape

	params = ExperimentParams(net_name,shape_X_train,shape_Y_train,target_vars,tr_epochs)
	param_file = basename+'%dEp_Fold%d_Of_%d'%(tr_epochs,current_fold,N_folds)

	with open(param_file, 'wb') as output:
		pickle.dump(params, output)

	test_error = net.test_model(X_test,y_test)
	train_error = net.test_model(X_train_cnn,y_train_cnn)

	print test_error
	print train_error

	others = dict()

	others['acc_val']= smetrics.acc_val
	#others['acc_tr']= smetrics.acc_tr

	others['prec_val']= smetrics.prec_val
	#others['prec_tr']= smetrics.prec_tr

	others['rec_val']= smetrics.rec_val
	#others['rec_tr']= smetrics.rec_tr

	tr_accs[counter,:] = history_tr_acc
	ts_accs[counter,:] = smetrics.acc_val
	precisions[counter,:] = np.array(smetrics.prec_val)
	recalls[counter,:] = np.array(smetrics.rec_val)

	allress = np.dstack((ts_accs[:,0],precisions[:,0],recalls[:,0]))
	print allress

	counter +=1

	results = ExperimentResults(train_error,test_error,history_tr_acc,history_val_acc,others)

	with open(results_file, 'wb') as output:
		pickle.dump(results, output)

	#Save trained model
	if not os.path.isdir(save_dir):
	    os.makedirs(save_dir)
	model_path = os.path.join(save_dir, str(current_fold)+'_'+model_name)
	net.save(model_path)
	print('Saved trained model at %s ' % model_path)

	#Saves Experiment Test index
	teststr = str(current_fold)+'_TEST_'+model_name+'.csv'
	teststr_path = os.path.join(save_dir, teststr)
	with open(teststr_path,"w+") as my_csv:
	    csvWriter = csv.writer(my_csv,delimiter=',')
	    for tesx in test_pullbacks:
	    	csvWriter.writerow([tesx])

	#Saves Experiment Train index
	teststr = str(current_fold)+'_TRAIN_'+model_name+'.csv'
	teststr_path = os.path.join(save_dir, teststr)
	with open(teststr_path,"w+") as my_csv:
	    csvWriter = csv.writer(my_csv,delimiter=',')
	    for tesx in train_pullbacks_cnn:
	    	csvWriter.writerow([tesx])
	current_fold+=1

	del net

#Saves Experiment Precision and Recall
with open(name_performance_csv,"w+") as my_csv:
    csvWriter = csv.writer(my_csv,delimiter=',')
    csvWriter.writerows(allress[0])
