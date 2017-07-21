#!/usr/bin/env python2
#
# License: GPL2
# Copyright Mark "Klowner" Riedesel
# https://github.com/Klowner/inkscape-applytransforms
#
import sys
sys.path.append('/usr/share/inkscape/extensions')

import inkex
import cubicsuperpath
import math
import simplestyle
from simpletransform import composeTransform, fuseTransform, parseTransform, applyTransformToPath, applyTransformToPoint, formatTransform
import re

def ePrint(msg):
    sys.stderr.write(str(msg) + "\n")
    

class ApplyTransform(inkex.Effect):
    def __init__(self):
        inkex.Effect.__init__(self)

    def effect(self):
        self.getselected()

        if self.selected:
            for id, shape in self.selected.items():
                self.recursiveFuseTransform(shape, parseTransform(None))
        else:
            self.recursiveFuseTransform(self.document.getroot(), parseTransform(None))

    @staticmethod
    def objectToPath(node):
        if node.tag == inkex.addNS('g', 'svg'):
            return node

        if node.tag == inkex.addNS('path', 'svg') or node.tag == 'path':
            for attName in node.attrib.keys():
                if ("sodipodi" in attName) or ("inkscape" in attName):
                    del node.attrib[attName]
            return node

        return node

    # a dictionary of unit to user unit conversion factors - copied from inkex. We actually only need the unit names here
    __uuconv = {'in': 96.0, 'pt': 1.33333333333, 'px': 1.0, 'mm': 3.77952755913, 'cm': 37.7952755913,
                'm': 3779.52755913, 'km': 3779527.55913, 'pc': 16.0, 'yd': 3456.0, 'ft': 1152.0}

    def getUnit(self, string):
        unit = re.compile('(%s)$' % '|'.join(self.__uuconv.keys()))
        u = unit.search(string)    
        if u:
            try:
                return u.string[u.start():u.end()]
            except KeyError:
                pass
        return self.getDocumentUnit()
    
    def getVal(self, string):
        return self.unittouu(self.addDocumentUnit(string))
    
    def valWithUnit(self, val, unit):
        if unit == self.getDocumentUnit():
            return str(val)
        else:
            return str(self.uutounit(val, unit)) + unit

    def recursiveFuseTransform(self, node, transf=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]):
        transf = composeTransform(transf, parseTransform(node.get("transform", None)))

        if 'transform' in node.attrib:
            del node.attrib['transform']

        if 'style' in node.attrib:
            style = node.attrib.get('style')
            style = simplestyle.parseStyle(style)
            update = False

            if 'stroke-width' in style:
                unit = self.getUnit(style.get('stroke-width').strip())
                stroke_width = self.getVal(style.get('stroke-width').strip())
                # pixelsnap ext assumes scaling is similar in x and y
                # and uses the x scale...
                # let's try to be a bit smarter
                stroke_width *= math.sqrt((transf[0][0]**2 + transf[1][1]**2)/2)

                style['stroke-width'] = self.valWithUnit(stroke_width, unit)
                update = True

            if update:
                style = simplestyle.formatStyle(style)
                node.attrib['style'] = style

        node = ApplyTransform.objectToPath(node)

        if 'd' in node.attrib:
            d = node.get('d')
            p = cubicsuperpath.parsePath(d)
            applyTransformToPath(transf, p)
            node.set('d', cubicsuperpath.formatPath(p))

        elif node.tag == inkex.addNS('polygon', 'svg'):
            points = node.get('points')
            points = points.strip().split(' ')
            for k,p in enumerate(points):
                p = p.split(',')
                unit = self.getUnit(p[0])
                p = [self.getVal(p[0]),self.getVal(p[1])]
                applyTransformToPoint(transf, p)
                p = [self.valWithUnit(p[0],unit),self.valWithUnit(p[1],unit)]
                p = ','.join(p)
                points[k] = p
            points = ' '.join(points)
            node.set('points', points)

        # if there is cx, there is also cy
        if 'cx' in node.attrib:
            cx = node.get('cx')
            cy = node.get('cy')
            unit = self.getUnit(cx)
            pt = [self.getVal(cx), self.getVal(cy)]
            applyTransformToPoint(transf, pt)
            node.set('cx', self.valWithUnit(pt[0],unit))
            node.set('cy', self.valWithUnit(pt[1],unit))
            
        if 'r' in node.attrib:
            unit = self.getUnit(node.get('r'))
            r = self.getVal(node.get('r'))
            # this is a circle: is the scale uniform?
            if transf[0][0] == transf[1][1]:
                r *= abs(transf[0][0])
                node.set('r', self.valWithUnit(r, unit))
            else:
                # transform is not uniform: go from circle to ellipse
                # NOTE!!! Inkscape currently applies this particular transform as soon as we touch the object.
                # therefore rx and ry are both assigned to r, otherwise the scaling is applied two times!
                # this is kind of a bug of the implementation
                rx = r #*abs(transf[0][0])
                ry = r #*abs(transf[1][1])
                node.set('rx', self.valWithUnit(rx, unit))
                node.set('ry', self.valWithUnit(ry, unit))
                del node.attrib['r']
                node.tag = inkex.addNS('ellipse', 'svg')

        if 'rx' in node.attrib:
            unit = self.getUnit(node.get('rx'))
            rx = self.getVal(node.get('rx'))*abs(transf[0][0])
            ry = self.getVal(node.get('ry'))*abs(transf[1][1])
            node.set('rx', self.valWithUnit(rx, unit))
            node.set('ry', self.valWithUnit(ry, unit))
            
            
        if 'x' in node.attrib: 
            unit = self.getUnit(node.get('x'))
            x = self.getVal(node.get('x'))*transf[0][0]
            y = self.getVal(node.get('y'))*transf[1][1]
            node.set('x', self.valWithUnit(x, unit))
            node.set('y', self.valWithUnit(y, unit))
            
        if 'width' in node.attrib: 
            unit = self.getUnit(node.get('width'))
            w = self.getVal(node.get('width'))*transf[0][0]
            h = self.getVal(node.get('height'))*transf[1][1]
            if w < 0:
                xUnit = self.getUnit(node.get('x'))
                x = self.getVal(node.get('x'))
                x += w;
                w = -w;
                node.set('x', self.valWithUnit(x, xUnit))
            if h < 0:
                yUnit = self.getUnit(node.get('y'))
                y = self.getVal(node.get('y'))
                y += h;
                h = -h;
                node.set('y', self.valWithUnit(y, yUnit))
            node.set('width', self.valWithUnit(w, unit))
            node.set('height', self.valWithUnit(h, unit))
        


        for child in node.getchildren():
            self.recursiveFuseTransform(child, transf)


if __name__ == '__main__':
    e = ApplyTransform()
    e.affect()
