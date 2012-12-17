import sys
import SizeAlgorithm
import ReadVector
from KB import Prototypes
from KB import Size
import webcolors
import random

class Fixate():
    def __init__(self, o):
        # Object is first represented in terms of its visual features.
        # (orientations, intensities, edges, corners, opacity, sheen) = object 
        # Low-level visual properties are those that only have lemmas
        # in combination (e.g., orientation + edges -> shape)
        # Object is now "an object", as such.
        # represented as a set of simple and complex properties, 
        # each with attributes and values
        self.object = o
    
    def __getitem__(self, key):
        return self.object[key]

class Refer():
    def __init__(self, object, scene, alpha_file, PO_file):
        self.known_attributes = {}
        (self.SP, self.CP) = self.do_PO(PO_file)
        self.all_props = self.SP + self.CP
        self.cat = None
        self.type = None
        self.g = 5
        self.a = 1
        self.alpha = self.read_alpha(alpha_file)
        #self.beta['color']['red'] = .5
        #self.beta['color']['orange'] = .5
        #self.beta['color']['yellow'] = .5
        #self.beta['color']['green'] = .5
        #self.beta['color']['blue'] = .5
        #self.beta['color']['purple'] = .5
        #self.beta['color']['black'] = .5
        #self.beta['color']['white'] = .5
        #self.beta['color']['grey'] = .5
        #self.beta['color']['material'] = .5
        # The size algorithm
        self.calc_size = SizeAlgorithm.SizeAlgorithm()
        # The knowledge base
        self.protoKB = Prototypes()
        self.protohash = self.protoKB.protohash
        self.refer(object, scene)
    
    def do_PO(self, PO_file):
        SP_atts = ["colour", "size", "location", "orientation"]
        CP_atts = ["shape", "material", "texture", "sheen", "form", "opacity"]
        SP = []
        CP = []
        if PO_file == None:
            SP = SP_atts
            CP = CP_atts
        else:
            SP = []
            po = open(PO_file, "r").read()
            po = po.strip()
            po = po.split()
            for att in po:
                if att in SP_atts:
                    SP += [att]
                elif att in CP_atts:
                    CP += [att]
        return (SP, CP)
    
    def refer(self, obj, scene):
        # -- Parallel process 1 --
        r = []
        # Get the object category from visual similarity (type, with typical properties)
        self.cat = self.protoKB.find_category(obj)
        if self.cat != None:
            self.type = self.cat['type']
        else:
            # Unsure of object:
            # Placeholder lemma that would correspond to the surface form, e.g., "thing" 
            self.type = "thing"
        # -- Parallel process 2 --
        r = self.analyze_simple_properties(obj, scene, r)
        r = self.analyze_complex_properties(obj, scene, r)
        r += [('type', self.type)]
        self.generate_reference(r)

    def analyze_simple_properties(self, obj, scene, r):
        # -- Parallel process 1.1 --
        # Attributes are represented as multi-featured vectors.
        # For color, this includes luminances and intensities
        att = "colour"
        val = self.do_attribute(obj, scene, att)
        self.known_attributes[att] = val
        for i_att in self.protoKB.interconnections:
            # All at once....in parallel....But it's only material in testing, so it shouldn't matter
            if att in self.protoKB.interconnections[i_att]:
                i_val = self.do_attribute(obj, scene, i_att)
                self.known_attributes[i_att] = i_val
                try:
                    if att in self.protoKB.implies[(i_att, i_val)]:
                        if val in self.protoKB.implies[(i_att, i_val)][att] or val == self.protoKB.implies[(i_att, i_val)][att]:
                            if self.cat != None and self.type in self.protohash:
                                try:
                                    if i_val in self.protohash[self.type][i_att]:
                                        beta = self.protohash[self.type][i_att][i_val]
                                    else:
                                        # Equivalent to saying it is ATYPICAL, so mention it.
                                        beta = 0.0
                                except KeyError:
                                    # No stored typical things for this attribute; treat it as unremarkable.
                                    beta = 1.0
                                go = self.throw_dice(self.alpha[i_att], self.val_salience(att, val), len(r), beta)
                            if go:
                                r += self.lemma(i_val, i_att)
                except KeyError:
                    continue
        if self.cat != None and self.type in self.protohash:
            try:
                if val in self.protohash[self.type][att]:
                    beta = self.protohash[self.type][att][val]
                else:
                    # Equivalent to saying it is ATYPICAL, so mention it.
                    beta = 0.0
            except KeyError:
                # No stored typical things for this attribute; treat it as unremarkable.
                beta = 1.0
            go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len(r), beta)
            if go:
                r += self.lemma(val, att)
        else:
            go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len(r))
        if go:
            r += self.lemma(val, "colour")
        # -- Parallel process 1.2 --
        # Compare with other items in the scene for relative properties. 
        # Here the relative attribute is size.
        # It is an open question how to compare the stored typical
        # size of the object to the sizes of items of the same type
        # in the scene; for now I make the simplifying assumption that 
        # contrast set is the main factor.
        for att in ('size', 'location', 'orientation'):
            # Different classifier/algorithm for each kind of attribute
            # The size algorithm is from my size work.
            val = self.do_attribute(obj, scene, att)
            self.known_attributes[att] = val
            len_r = len(r)
            # Equivalent to a parallel process.
            if att == 'size':
                len_r = 0
            if val == "Unknown":
                continue
            if self.cat != None:
                go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len_r)
            else:
                go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len_r)
            if go:
                r += self.lemma(val, att)
        return r

    def analyze_complex_properties(self, obj, scene, r):
        # Should this be parallel or incremental?  
        # Probably associated to lemmas incrementally, so we will run this
        # incrementally.
        # So we need a preference order for this, don't we?  Yes.
        #print "CP is", self.CP
        for att in self.CP:
            if att not in self.known_attributes:
                # Different classifier/algorithm for each kind of attribute
                val = self.do_attribute(obj, scene, att)
                self.known_attributes[att] = val
            else:
                val = self.known_attributes[att]
            if val == "Unknown": continue
            val_salience = 0
            if self.cat != None and self.type in self.protohash:
                #sys.stderr.write("Considering " + att + "\n")
                try:
                    if val in self.protohash[self.type][att]:
                        beta = self.protohash[self.type][att][val]
                    else:
                        # Equivalent to saying it is ATYPICAL, so mention it.
                        beta = 0.0
                except KeyError:
                    # No stored typical things for this attribute; treat it as unremarkable.
                    beta = 1.0
                #sys.stderr.write("Input beta is " + str(beta) + "\n")
                go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len(r), beta)
                #print go
                #if not go:
                #        sys.stderr.write("no go\n")
            else:
                go = self.throw_dice(self.alpha[att], self.val_salience(att, val), len(r))
            if go:
                r += self.lemma(val, att)
        # Each object is examined incrementally,
        # following the original idea in Pechmann [1989] 
        for d in scene:
            d_obj = Fixate(scene[d])
            d_cat = self.protoKB.find_category(d_obj)
            if d_obj['pos'] == obj['pos']:
                continue
            if self.cat:
                if d_cat['type'] == self.type:
                    for att in self.all_props:
                        #print att
                        d_val = self.do_attribute(d_obj, scene, att)
                        t_val = self.known_attributes[att]
                        if t_val == "Unknown": continue
                        if d_val != t_val:
                            l = self.lemma(t_val, att, d_val)
                            # Don't add something we've already said.
                            if l[0] in r:
                                continue
                            go = self.throw_dice(1, 1, len(r))
                            if go:
                                #print "After comparison, adding", l
                                r += l
        return r
            
    def do_attribute(self, obj, scene, att):
        # Just gold-standard for now:  We know the "real"
        # value of the attribute.
        #if att == "color":
        #    c = obj['colors']
        #    l = obj['luminances']
        #    i = obj['intensities']
        #    val = self.__get_color__(c, l, i)
        if att == "size":
            h = obj['height']
            w = obj['width']
            val = self.__get_size__(h, w, obj, scene)
        else:
            val = obj[att]
        return val

    def lemma(self, val, att, d_val=None):
        if att == 'size':
            val = Size(val).lemma
        return [(att, val)]
    
    def throw_dice(self, alpha, val_salience, penalty, beta=1.0):
        weight_function = 1
        if penalty == 0:
            gamma = 1
        else:
            gamma = 1/(float(penalty) * self.g)
        alpha *= self.a
        delta = val_salience
        # Playing with this
        # gamma = self.num_mods[penalty]
        #sys.stderr.write("alpha is " + str(alpha) + " delta is " + str(delta) + " gamma is " + str(gamma) + " beta is " + str(beta) + "\n")
        weight_function = alpha * delta * gamma + ((1 - beta) * (1 - (alpha * delta)))
        #print "alpha:", alpha, "beta:", beta
        #print weight_function
        #sys.stderr.write("weight function is " +  str(weight_function) + "\n")
        # What if I just do this?
        # weight_function = alpha
        n = random.random()
        #print "weight_function is", weight_function, "n is", n
        if n < weight_function:
            return True
        else:
            return False

    def val_salience(self, att, val):
        if att == "colour":
            return 1
        elif att == "size":
            return 1
        return 1
                
    def read_alpha(self, f):
        alpha_hash = {}
        o = open(f, "r")
        r_o = o.readlines()
        o.close()
        tmp_hash = {}
        for feat in r_o:
            feat = feat.strip()
            feat = feat.split(":")
            att = feat[0]
            weight = float(feat[1])
            tmp_hash[att] = weight
        for att in self.all_props:
            if att not in tmp_hash:
                tmp_hash[att] = 0.0
        alpha_hash = tmp_hash
        return alpha_hash

    def __get_distractors__(self, obj, scene):
        d = []
        for object_id in scene:
            d_object = scene[object_id]
            # Should actually be a function of the similarity....
            if d_object['pos'] != obj['pos']:
                if d_object['type'] == self.type:
                    d += [d_object]
        return d

    def __average__(self, distractors):
        h = 0.0
        w = 0.0
        for o in distractors:
            h += float(o['height'])
            w += float(o['width'])
        h /= float(len(distractors))
        w /= float(len(distractors))
        return (h, w)

    def __get_size__(self, h, w, obj, scene):
        height = float(h)
        width = float(w)
        distractors = self.__get_distractors__(obj, scene)
        #print distractors
        # Ariely (1990?), Oliva and Torralba
        if distractors != []:
            (contrast_height, contrast_width) = self.__average__(distractors)
            (mod, pol) = self.calc_size.size_mod(width, height, contrast_width, contrast_height) 
            size = (mod, pol)
            return size
        return None

    def generate_reference(self, ref):
        for (att, val) in ref:
            if val == "Unknown":
                continue
            if val:
                print val,
        print "\t\t+",
        said = {}
        for (att, val) in ref:
            if val == None or val == "":
                continue
            if (att, val) in said:
                continue
            print "tg" + ":" + att + ":" + val,
            said[(att, val)] ={}
        print ""

def main(scene, desired_object_id, alpha_file, beta_file):
    # A scene is formalized as a series of objects composed of visual properties 
    # A single object is a member of the scene
    fixation = Fixate(scene[desired_object_id])
    object = fixation.object
    reference = Refer(object, scene, alpha_file, beta_file)
    #p = analyze_parts()

if __name__ == '__main__':
    s = ReadVector.Read(sys.argv[1])
    alpha_file = sys.argv[2]
    try:
        PO_file = sys.argv[3]
    except IndexError:
        PO_file = None
    scene = s.scene
    desired = '1'
    main(scene, desired, alpha_file, PO_file)
