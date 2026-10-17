import sys, os, glob
from PIL import Image
from multiprocessing import Pool
def conv(p):
    j = p[:-4] + ".jpg"
    if not os.path.exists(j):
        Image.open(p).convert("RGB").save(j, quality=93, subsampling=0)
    return j
if __name__ == "__main__":
    cuts = sys.argv[1:]
    files = [f for c in cuts for f in sorted(glob.glob(os.path.expanduser(f"~/movie/frames/{c}/f*.png")))]
    with Pool(3) as pool:
        for i, _ in enumerate(pool.imap_unordered(conv, files, chunksize=8)):
            pass
    print("converted", len(files))
