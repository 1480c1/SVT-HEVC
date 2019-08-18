#!/usr/bin/env python

# Copyright(c) 2018 Intel Corporation
# SPDX - License - Identifier: BSD - 2 - Clause - Patent

"""
Run tests for SvtHevcEncApp
"""

from __future__ import print_function

import errno
import hashlib
import multiprocessing
import os
import getopt
import platform
import signal
import subprocess
import sys


def signal_handler():
    """Intercept signals and terminate using sys.exit(0)"""
    print("Terminating test")
    sys.exit(0)


def print_help():
    print()


def parse_args(argv):
    try:
        opts, args = getopt.getopt(
            argv, "ht:", ["fast", "Fast", "nightly", "Nightly", "full", "Full"])
    except getopt.GetoptError:
        VALIDATION_TEST_MODE = 0
    for opt, arg in opts:
        if opt == '-h':
            print_help()
            sys.exit()
        elif opt in ("-t"):
            if arg in ("fast", "Fast"):
                VALIDATION_TEST_MODE = 0
            elif arg in ("nightly", "Nightly"):
                VALIDATION_TEST_MODE = 1
            elif arg in ("full", "Full"):
                VALIDATION_TEST_MODE = 2
        elif opt in ("fast", "Fast"):
            VALIDATION_TEST_MODE = 0
        elif opt in ("nightly", "Nightly"):
            VALIDATION_TEST_MODE = 1
        elif opt in ("full", "Full"):
            VALIDATION_TEST_MODE = 2


def get_pix_fmt(pix_fmt):
    """Convert pix_fmt of chromaBit to either gst format or ffmpeg"""
    if GST_LAUNCH:
        gst_pix_fmts = {
            "420": "I420",
            "42010": "I420_10LE",
            "42012": "I420_12LE",
            "42210": "I422_10LE",
            "42212": "I422_12LE",
            "444": "Y444",
            "44410": "Y444_10LE",
            "44412": "Y444_12LE"
        }
        return gst_pix_fmts.get(pix_fmt, "")
    else:
        ffmpeg_pix_fmts = {
            "420": "yuv420p",
            "42010": "yuv420p10le",
            "42012": "yuv420p12le",
            "42210": "yuv422p10le",
            "42212": "yuv422p12le",
            "444": "yuv444p",
            "44410": "yuv444p10le",
            "44412": "yuv444p12le"
        }
        return ffmpeg_pix_fmts.get(pix_fmt, "")


def exec_exists(program, *hints):
    """Tests and prints the program path if it exists in PATH or in current directory or in hints"""
    if platform.system() == "Windows":
        program = program + ".exe"
    if os.path.exists(program):
        return os.path.abspath(program)
    paths_to_check = os.environ["PATH"].split(os.pathsep)
    for hint in hints:
        paths_to_check.append(hint)
    for path in paths_to_check:
        exe_file = os.path.join(path, program)
        if os.path.isfile(exe_file) and os.access(exe_file, os.X_OK):
            return exe_file
    return ""


def get_hash(hash_type, file_to_be_hashed, bytes_to_read=100):
    """Get the hash of a file"""
    if not os.path.exists(file_to_be_hashed):
        return ""
    file_to_be_hashed_stream = open(file_to_be_hashed, "rb")
    if bytes_to_read == 0:
        file_bytes = file_to_be_hashed_stream.read()
    else:
        file_bytes = file_to_be_hashed_stream.read(bytes_to_read)

    if hash_type == "sha512":
        video_hash = hashlib.sha512(file_bytes).hexdigest()
    elif hash_type == "sha384":
        video_hash = hashlib.sha384(file_bytes).hexdigest()
    elif hash_type == "sha256":
        video_hash = hashlib.sha256(file_bytes).hexdigest()
    elif hash_type == "sha224":
        video_hash = hashlib.sha224(file_bytes).hexdigest()
    elif hash_type == "sha1":
        video_hash = hashlib.sha1(file_bytes).hexdigest()
    else:
        video_hash = hashlib.md5(file_bytes).hexdigest()

    file_to_be_hashed_stream.close()
    return video_hash


def check_file(file_to_be_checked, hash_type, bytes_to_read, *args):
    # To use to compare the output files
    """Check if file matches hash"""
    if not os.path.exists(file_to_be_checked):
        return False
    for hash_to_check in args:
        if get_hash(hash_type=hash_type,
                    file_to_be_hashed=file_to_be_checked,
                    bytes_to_read=bytes_to_read) == hash_to_check:
            return True
    return False


def generate_video(width=7680, height=4320, bit_depth=8, fps=25, pix_fmt="420"):
    """
    Generate test yuv video using either gst-launch-1.0 or ffmpeg
    """
    pix_fmt = get_pix_fmt(str(pix_fmt))
    output_file = "test_" + str(width) + "x" + str(height) + "_" + str(bit_depth) + "bit_" + \
        str(fps) + "Hz_" + str(pix_fmt) + ".yuv"
    try:
        output_file_stream = open(output_file, "w")
        output_file_stream.close()
    except IOError:
        if IOError.errno == errno.EACCES:
            print("Failed to open {}, you lack permissions".format(output_file))
            sys.exit(1)
        elif IOError.errno == errno.EISDIR:
            print("Failed to open {}, it is a directory".format(output_file))
            sys.exit(1)

    print("Generating {}".format(output_file), end=" ")
    dev_null = open(os.devnull, "w")

    if GST_LAUNCH:
        print("using gst-launch-1.0")
        exit_code = subprocess.call(
            [GST_LAUNCH, "videotestsrc", "num-buffers={}".format(10 * fps),
             "!", "video/x-raw,", "framerate={}/1,".format(fps),
             "width={},".format(width), "height={}".format(height),
             "!", "filesink", "location={}".format(output_file)])
    else:
        print("using ffmpeg")
        exit_code = subprocess.call(
            [FFMPEG_EXEC, "-y", "-threads", "{}".format(multiprocessing.cpu_count()),
             "-f", "lavfi", "-i",
             "testsrc=duration=10:size={}x{}:rate={}".format(
                 width, height, fps),
             "-pix_fmt", "yuv420p", output_file])

    dev_null.close()
    if exit_code != 0:
        print("Failed generating {}".format(output_file))
        sys.exit(1)

    if os.path.exists(output_file):
        return output_file
    return ""


def run_enc(source_file="8k.yuv", width=7680, height=4320, fps=25):
    command_args = SVTHEVCENCAPP + " -i " + str(source_file) + \
        " -w " + str(width) + " -h " + str(height) + " -fps " + str(fps)
    print("Encoding " + source_file, end=' ')
    output_file = os.path.splitext(source_file)[0]+".h265"
    command_args = command_args + " -b " + output_file
    print("to " + output_file)
    print()
    print(command_args)
    if SVTHEVCENCAPP:
        subprocess.call(command_args.split())

# def run_dec(source_file, width, height, fps):
#    command_args = TAPPDEC


def generate_test_videos():
    # Needs to be separated out by test mode
    """Generate test video sequences to encode"""
    generate_video(864, 480, 8, 50, "420")
    generate_video(864, 480, 8, 50, "42010")
    generate_video(1280, 720, 8, 50, "420")
    generate_video(1280, 720, 8, 60, "420")
    generate_video(1920, 1080, 8, 60, "420")
    generate_video(3840, 2160, 10, 60, "420")
    generate_video(4096, 2160, 10, 60, "420")
    generate_video(7680, 4320, 10, 30, "420")


# def run_test(width, height, fps, bit_depth,):
#    run_enc()


SVTHEVCENCAPP = exec_exists("SvtHevcEncApp")
TAPPDEC = exec_exists("TAppDecoder")
GST_LAUNCH = exec_exists("gst-launch-1.0")
FFMPEG_EXEC = exec_exists("ffmpeg")

if not (GST_LAUNCH or FFMPEG_EXEC):
    print("Can't find gst-launch-1.0 or ffmpeg")
    sys.exit(2)
signal.signal(signal.SIGINT, signal_handler)  # Capture ctrl + c

generate_video()
run_enc()
