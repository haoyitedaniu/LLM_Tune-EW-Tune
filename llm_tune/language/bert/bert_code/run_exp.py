import os
from privacy_tools import get_sigma
import argparse
import subprocess

parser = argparse.ArgumentParser(description='differentially private BERT finetuning')

parser.add_argument('--task', default='SST-2', type=str, help='task name, choices: [MNLI, QNLI, QQP, SST-2]') ## default SST-2
parser.add_argument('--gpu_id', default=0, type=int, help='GPU id')
parser.add_argument('--ckpt_dir', type=str, default='~/roberta.base/model.pt', help='path to checkpoint') ## default roberta.large (not for MNLI due to memory)
parser.add_argument('--output_dir', default='log_dir', type=str, help='output path')
parser.add_argument('--data_dir', type=str, default='../glue_data', help='data path prefix')
parser.add_argument('--to_console', action='store_true', help='output to console')
parser.add_argument('--sess', type=str, default='default', help='session name')

#standard config
parser.add_argument('--seed', default=3, type=int, help='random seed')
parser.add_argument('--lr', default=3e-4, type=float, help='base learning rate')
parser.add_argument('--batch_size', default=2000, type=int, help='batch size') 
parser.add_argument('--epoch', default=20, type=int, help='number of epochs') ## default: 50
parser.add_argument('--max_sentences', default=50, type=int, help='max sentences per step. Use smaller value if your GPU runs out of memory')# default 50
parser.add_argument('--weight_decay', default=0., type=float, help='weight decay')
parser.add_argument('--warmup_ratio', default=0.0, type=float, help='warmup ratipo')
parser.add_argument('--dropout', default=0.1, type=float, help='dropout value')

#privacy config
parser.add_argument('--eps', default=7, type=float, help='DP parameter epsilon')
parser.add_argument('--delta', default= 1e-5, type=float, help='DP parameter delta') ## default = 1e-5
parser.add_argument('--clip', default=10., type=float, help='clipping threshold of individual gradients')
parser.add_argument('--rank', default=1, type=int, help='reparameterization rank')
parser.add_argument('--linear_eval', action='store_true', help='use linear evaluation or not')
parser.add_argument('--accountant', type=str, default='prv', help='which accountant to use') ## default='prv'

args = parser.parse_args()

assert args.task in ['MNLI', 'QNLI', 'QQP', 'SST-2', 'CoLA', 'STS-B', 'MRPC', 'RTE']



args.data_dir += '/%s-bin'%args.task

metric='accuracy'
n_classes=2
if(args.linear_eval):
    apdx = ' --linear_eval '
else:
    apdx = ''


if(args.task == 'MNLI'):
    n_classes = 3
    apdx += ' --valid-subset valid,valid1 '
elif(args.task == 'CoLA'):
    metric='mcc'
elif(args.task == 'STS-B'):
    metric = 'pearson_spearman'
    apdx += ' --regression-target '
    n_classes = 1

assert args.batch_size % args.max_sentences == 0

update_freq = args.batch_size // args.max_sentences

dataset_size_dict ={'MNLI':392702, 'QQP':363849, 'QNLI':104743, 'SST-2':67349, 'CoLA':8551, 'STS-B':5700, 'MRPC':3500, 'RTE':2500}
dataset_size = dataset_size_dict[args.task]

if(dataset_size < 10000):
    print('The dataset is too small, you are probably going to see some bad results. Try larger dataset such as [MNLI, QNLI, QQP, SST-2]')

if(args.eps > 0):
    q = args.batch_size/dataset_size
    steps = args.epoch * (dataset_size//args.batch_size)
    sigma, eps = get_sigma(q, steps, args.eps, args.delta, mode=args.accountant)

    print('noise std:', sigma, 'eps: ', eps)
else:
    sigma = -1
    eps = -1

output_cmd = ' >> '
if(args.to_console):
    output_cmd = ' 2>&1 | tee '

sess = args.sess

arch = 'roberta_base'
if('large' in args.ckpt_dir):
    arch = 'roberta_large'

os.system('mkdir -p %s/%s'%(args.output_dir, args.task))
#--warmup-ratio %f
cmd = 'CUDA_VISIBLE_DEVICES=%d /home/eb/anaconda3/envs/ppml/bin/python3 train.py %s \
        --restore-file %s \
        --max-positions 512 --clip %f --sigma %f \
        --max-sentences %d --update-freq %d \
        --rank %d --max-tokens 8000 \
        --task sentence_prediction \
        --reset-optimizer --reset-dataloader --reset-meters \
        --required-batch-size-multiple 1 \
        --init-token 0 --separator-token 2 \
        --arch roberta_base \
        --criterion sentence_prediction %s \
        --num-classes %d \
        --dropout %f --attention-dropout %f \
        --weight-decay %f --optimizer adam --adam-betas "(0.9,0.999)" --adam-eps 1e-06 \
        --clip-norm 0 --validate-interval-updates 1 \
        --lr-scheduler polynomial_decay --lr %f --warmup-ratio %f --sess %s \
        --max-epoch %d --seed %d --save-dir %s --no-progress-bar --log-interval 100 --no-epoch-checkpoints --no-last-checkpoints --no-best-checkpoints \
        --find-unused-parameters --skip-invalid-size-inputs-valid-test --truncate-sequence --embedding-normalize  \
        --tensorboard-logdir . --bert-pooler --pooler-dropout %f \
        --best-checkpoint-metric %s --maximize-best-checkpoint-metric %s %s/%s/%s_train_log_test.txt'%(args.gpu_id, args.data_dir, args.ckpt_dir, args.clip, sigma, args.max_sentences, update_freq, args.rank, apdx, n_classes, args.dropout, args.dropout, args.weight_decay, args.lr, args.warmup_ratio, sess, args.epoch, args.seed, args.output_dir, args.dropout, metric, output_cmd, args.output_dir, args.task, sess)

##cmd = "python3 --version"
print(os.getcwd())


os.system(cmd)

# def run_cmd(cmd, verbose=False, *args, **kwargs):
#     """
#     Run system command as a subprocess
#     """
#     process = subprocess.Popen(cmd, 
#                                stdout = subprocess.PIPE,
#                                stderr = subprocess.PIPE,
#                                text = True,
#                                shell = True)
#     std_out, std_err = process.communicate()
#     if verbose:
#         print(std_out.strip(), std_err)
#
# run_cmd('echo "Running cmd!"', verbose = True)

