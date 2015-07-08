import pychartdir
from pychartdir import *

#  Activate ChartDirector License
pychartdir.setLicenseCode('DEVP-2HYW-CAU5-4YTR-6EA6-57AC')

from pychartdir import Center, Left, TopLeft, DataColor, XYChart, PieChart

if __name__ == "__main__":
    data = [10,20,30,40,50,60,50,40,30,40,50,60]
    labels = ["foo", "bar", "baz", "qux", "quux", "corge", "grault", "garply"]

    c = XYChart(2000, 1000)
    c.setPlotArea(200, 200, 1600, 700, c.linearGradientColor(0, 0, 0, 1000, 0x008e44,
    0xFFFFFF))
    c.setColors2(DataColor, [0x9bbb59]) 
    layer = c.addBarLayer(data)
    layer.setBorderColor(Transparent, glassEffect(NormalGlare, Left, 20))
    layer.set3D(40)
    c.addTitle2(TopLeft, "Period Production", "verdanab.ttf", 72, 0x000000).setMargin2(0, 0, 30, 0)
    c.yAxis().setLabelStyle('Inconsolata.ttf', 64)
    c.yAxis().setTickDensity(100)
    c.yAxis().setTitle("100 Thousand BTUs", 'Inconsolata.ttf', 52)
    c.xAxis().setLabels(labels)
    c.xAxis().setLabelStyle('Inconsolata.ttf', 24)
    c.makeChart("SampleGraph.png") 