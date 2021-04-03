# Ubuntu port of motion_supporter

## Installation (Ubuntu 20.04)

Install dependency libraries
```
sudo apt-get install python3 python3-pip python3-wxgtk4.0 python3-numpy
pip3 install numpy-quaternion bezier Cython
```

Clone and Build
```
git clone https://github.com/nagadomi/motion_supporter.git
cd motion_supporter
git submodule update --init --recursive
cd src
python3 setup.py build_ext --inplace
```

Run (Must be run in the root directory of the repository)
```
python3 src/executor.py
```


# Original README.md

# motion_supporter



## Dependencies

 - [numpy](https://pypi.org/project/numpy/)
 - [wxPython](https://pypi.org/project/wxPython/)
 - [numpy-quaternion](https://pypi.org/project/numpy-quaternion/)
 - [bezier](https://pypi.org/project/bezier/)

