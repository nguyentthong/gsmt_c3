## Requirements
- python3
- pandas
- gensim
- numpy
- torchvision
- pytorch 1.11.0
- scipy
- transformers
- numpy
- tqdm
- ffmpeg
- h5py
- decord
- opencv-python
- Pillow

## How to Run
1. Download and put the dataset in the ```gsmt_data``` folder: https://tinyurl.com/gsmt15042024
2. Train the model by running ```bash ./shells/train/{dataset}_gsmt.sh``` (egoqa or madqa)
3. Evaluate the model via executing ```bash ./shells/test/{dataset}_gsmt.sh``` (egoqa or madqa)
