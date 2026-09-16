"""Display original redacted source pixels; do not redraw historical text."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
from ocr import ROOT


def pages(case='a'):
    fig,axes=plt.subplots(1,2,figsize=(13,11),layout='constrained')
    for ax,period in zip(axes,('before','after')):
        with Image.open(ROOT/'data/pages'/f'sample-{case}-{period}.png') as im:
            ax.imshow(im)
        ax.set_title('Earlier source' if period=='before' else 'Later source')
        ax.axis('off')
    fig.suptitle('Real archival excerpts | city, year and source identifiers withheld',fontsize=14)
    return fig
