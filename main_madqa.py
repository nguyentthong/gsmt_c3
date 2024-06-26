import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import random
import os
import os.path as osp
import logging
import h5py
from transformers import get_cosine_schedule_with_warmup, BertTokenizer
from args import get_args
from model.gsmt_madqa import GSMT_VideoQA
from util import compute_a2v, save_to
from train.train_madqa import train, eval
from data.madqa_clip_patch_loader import get_videoqa_loaders
from tqdm import trange


def main(args):
    if not (os.path.isdir(args.save_dir)):
        os.makedirs(os.path.join(args.save_dir), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s"
    )
    logFormatter = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    rootLogger = logging.getLogger()
    fileHandler = logging.FileHandler(os.path.join(args.save_dir, "stdout.log"), "w+")
    fileHandler.setFormatter(logFormatter)
    rootLogger.addHandler(fileHandler)
    logging.info(args)

    bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

    a2id, id2a, a2v = None, None, None
    if not args.mc:
        a2id, id2a, a2v = compute_a2v(
            vocab_path=args.vocab_path,
            bert_tokenizer=bert_tokenizer,
            amax_words=args.amax_words,
        )
        logging.info(f"Length of Answer Vocabulary: {len(a2id)}")

    model = GSMT_VideoQA(
        bert_tokenizer=bert_tokenizer,
        feature_dim=args.feature_dim,
        word_dim=args.word_dim,
        N=args.n_layers,
        d_model=args.embd_dim,
        d_ff=args.ff_dim,
        h=args.n_heads,
        dropout=args.dropout,
        T=args.max_feats,
        Q=args.qmax_words,
        baseline=args.baseline,
        bnum=args.bnum,
        dataset=args.dataset,
        num_frames_in_feature_file=args.num_frames_in_feature_file,
    )
    model.cuda()
    logging.info("Using {} GPUs".format(torch.cuda.device_count()))

    if args.pretrain_path != "":
        model.load_state_dict(torch.load(args.pretrain_path))
        logging.info(f"Loaded checkpoint {args.pretrain_path}")
    logging.info(
        f"Nb of trainable params:{sum(p.numel() for p in model.parameters() if p.requires_grad)}"
    )

    (
        train_loader,
        val_loader,
        test_loader,
    ) = get_videoqa_loaders(args, args.features_path, a2id, bert_tokenizer, test_mode=args.test)

    if args.test:
        logging.info("number of test instances: {}".format(len(test_loader.dataset)))
    else:
        logging.info("number of train instances: {}".format(len(train_loader.dataset)))
        logging.info("number of val instances: {}".format(len(val_loader.dataset)))

    criterion = nn.CrossEntropyLoss(ignore_index=-1)

    params_for_optimization = list(p for n, p in model.named_parameters() if p.requires_grad and n.split('.')[1] != 'clip')

    optimizer = optim.Adam(
        params_for_optimization, lr=args.lr, weight_decay=args.weight_decay
    )
    criterion.cuda()

    if not args.test:
        scheduler = get_cosine_schedule_with_warmup(
            optimizer, 0, len(train_loader) * args.epochs
        )
        logging.info(
            f"Set cosine schedule with {len(train_loader) * args.epochs} iterations"
        )
        if args.pretrain_path != "":
            val_acc, results = eval(model, val_loader, a2v, args, test=False)  # zero-shot VideoQA
            save_path = osp.join(args.save_dir, 'val-res0.json')
            save_to(save_path, results)
        best_val_acc = 0 if args.pretrain_path == "" else val_acc
        best_epoch = 0

        for epoch in range(args.epochs):
            train(model, train_loader, a2v, optimizer, criterion, scheduler, epoch, args, bert_tokenizer)
            val_acc, results = eval(model, val_loader, a2v, args, test=False)
            if val_acc > best_val_acc:
                best_val_acc = val_acc
                best_epoch = epoch
                torch.save(
                    model.state_dict(), os.path.join(args.save_dir, "best_model.pth")
                )
                save_path = osp.join(args.save_dir, 'val-res.json')
                save_to(save_path, results)
            if args.dataset == 'webvid':
                ep_file = os.path.join(args.save_dir, f"e{epoch}.pth")
                torch.save(model.state_dict(), ep_file)
                logging.info('Save to ' + ep_file)
        logging.info(f"Best val model at epoch {best_epoch + 1}")
    else:
        test_acc, results = eval(model, test_loader, a2v, args, test=True)
        save_path = osp.join(args.save_dir, 'test-res.json')
        save_to(save_path, results)



if __name__ == "__main__":
    args = get_args()
    torch.backends.cudnn.enabled = False
    torch.cuda.manual_seed(args.seed)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    torch.backends.cudnn.benchmark = True
    main(args)
