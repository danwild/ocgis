from django import forms
#from climatedata import models
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render_to_response
from django.shortcuts import redirect
from django.core.exceptions import ValidationError
#from django.core.context_processors import csrf
from django.template.context import RequestContext
from shapely import wkt as shapely_wkt
from util.helpers import reverse_wkt, get_temp_path
import pdb
import os
import zipfile
from util.ncconv.experimental.helpers import get_wkt_from_shp, get_shp_as_multi,\
    reduce_to_multipolygon, keep
from climatedata.models import UserGeometryData, UserGeometryMetadata
from django.contrib.gis.geos.geometry import GEOSGeometry
from django.contrib.gis.geos.collections import MultiPolygon
from django.contrib.gis.geos.polygon import Polygon
from climatedata import models
from django.db import transaction
from shapely.geos import ReadingError
from util.ncconv.experimental.ocg_stat import OcgStat, OcgStatFunction
import urllib


CHOICES_AGGREGATE = [
    ('true','TRUE'),
    ('false','FALSE'),
]
CHOICES_SOP = [
    ('intersects','Intersects'),
    ('clip','Clip'),
]
CHOICES_EXT = [
    ('geojson','GeoJSON Text File'),
    ('csv','Comma Separated Value'),
    ('kcsv','Linked Comma Separated Value (zipped)'),
    ('shz','ESRI Shapefile (zipped)'),
    ('lshz','CSV-Linked ESRI Shapefile (zipped)'),
    ('kml','Keyhole Markup Language'),
    ('kmz','Keyhole Markup Language (zipped)'),
    ('sqlite','SQLite3 Database (zipped)')
]

def get_SpatialQueryForm(simulation_output):
    ## the dataset object contains the test values
    dataset = simulation_output.netcdf_variable.netcdf_dataset
    
    ## validators and custom field classes for the dynamic form ----------------
    
    def _validate_drange_lower(value):
        if value > dataset.temporal_max.date():
            raise(ValidationError('Lower date range exceeds maximum dataset date.'))
    
    def _validate_drange_upper(value):
        if value < dataset.temporal_min.date():
            raise(ValidationError('Upper date range less than minimum dataset date.'))
        
    class OcgWktField(forms.CharField):
    
        def clean(self,value):
            ## check the geometry is valid
            try:
                ## try to load the form input from WKT
                geom = shapely_wkt.loads(value)
                ## convert to the url format
                ret = reverse_wkt(value)
            ## try to find the AOI code
            except ReadingError:
                try:
                    ## return the meta code
                    user_meta = models.UserGeometryMetadata.objects.filter(code=value)
                    ## confirm it exists in the database
                    if len(user_meta) == 0: raise(ValidationError)
                    ## convert to shapely geometries. first, return the actual
                    ## geometries
                    geom = models.UserGeometryData.objects.filter(user_meta=user_meta)
                    geom = [shapely_wkt.loads(geom.geom.wkt) for geom in geom]
                    ## convert to format acceptable for the url
                    ret = value
                except ValidationError:
                    raise(ValidationError('Unable to parse WKT or locate unique geometry code.'))
            ## check that spatial operations will return data
            ogeom = shapely_wkt.loads(dataset.spatial_extent.wkt)
            igeom = reduce_to_multipolygon(geom)
            if not keep(igeom=ogeom,target=igeom):
                raise(ValidationError('Input geometry will return an empty intersection.'))
            
            return(ret)
        
    ## -------------------------------------------------------------------------
    
    class SpatialQueryForm(forms.Form):
        
        drange_lower = forms.DateField(
            required=True,
            initial='1/1/2000',
            label='Lower Date Range',
            validators=[_validate_drange_lower],
        )
        drange_upper = forms.DateField(
            required=True,
            initial='3/1/2000',
            label='Upper Date Range',
            validators=[_validate_drange_upper],
        )
        wkt_extent = OcgWktField(
            required=True,
            label='WKT Extent',
            widget=forms.Textarea(attrs={'cols': 80, 'rows': 10}),
            initial='POLYGON ((-104 39, -95 39, -95 44, -104 44, -104 39))',
#            initial='MULTIPOLYGON (((-101.4073932908307825 40.0010033647185850, -102.0515352914306817 39.9989183647166371, -102.0475452914269709 40.3426443650367617, -102.0476202914270374 40.4310773651191226, -102.0460312914255638 40.6973193653670791, -102.0469922914264487 40.7431303654097405, -102.0477392914271491 40.9980713656471707, -102.6212572919612853 41.0002143656491711, -102.6522712919901608 40.9981243656472216, -103.3829562926706700 41.0003163656492617, -103.5723162928470202 40.9996483656486390, -104.0517052932934945 41.0032113656519641, -104.0540122932956422 41.3880853660104009, -104.0555002932970154 41.5642223661744410, -104.0536152932952660 41.6982183662992298, -104.0535132932951683 41.9998153665801226, -104.0562192932976870 42.6146693671527430, -104.0561992932976665 43.0030623675144668, -103.5014642927810371 42.9986183675103320, -103.0058752923194874 42.9993543675110175, -102.7883842921169304 42.9953033675072405, -102.0867012914634415 42.9898873675021918, -101.2317372906671835 42.9868433674993611, -100.1981422897045775 42.9910953675033198, -99.5327902890849145 42.9923353675044737, -99.2539712888252552 42.9923893675045292, -98.4976512881208777 42.9917783675039544, -98.4574442880834226 42.9371603674530888, -98.3912042880217399 42.9201353674372328, -98.3103392879464195 42.8817943674015254, -98.1678262878136962 42.8395713673622041, -98.1448692877923179 42.8357943673586874, -98.1231172877720610 42.8202233673441839, -98.1218202877708450 42.8083603673331368, -98.0331402876882549 42.7691923672966539, -97.9951442876528773 42.7668123672944418, -97.9635582876234565 42.7736903673008442, -97.9294772875917232 42.7923243673182014, -97.8899412875548904 42.8312713673544749, -97.8886592875537076 42.8558073673773237, -97.8186432874884986 42.8665873673873676, -97.7970282874683647 42.8495973673715440, -97.7721862874452228 42.8461643673683454, -97.7252502874015221 42.8580083673793695, -97.6857522873647355 42.8368373673596565, -97.6349702873174436 42.8612853673824219, -97.5706542872575397 42.8479903673700449, -97.5061322871974454 42.8601363673813580, -97.4831592871760506 42.8571573673785764, -97.4572632871519318 42.8504433673723284, -97.3893062870886439 42.8674333673881520, -97.3114142870161061 42.8617713673828789, -97.2714572869788867 42.8500143673719265, -97.2431892869525569 42.8518263673736186, -97.2244432869350987 42.8412023673637208, -97.2118312869233563 42.8125733673370590, -97.1614222868764159 42.7986193673240649, -97.1304692868475854 42.7739233673010659, -97.0151392867401796 42.7595423672876649, -96.9795932867070718 42.7583133672865259, -96.9700032866981445 42.7520653672807072, -96.9778692867054701 42.7273083672576490, -96.9707732866988579 42.7211473672519162, -96.9082342866406066 42.7316993672617400, -96.8101402865492560 42.7040843672360211, -96.8104372865495293 42.6813413672148414, -96.7993442865391955 42.6700193672042900, -96.7226582864677766 42.6685923672029617, -96.6990602864457998 42.6577153671928357, -96.6945962864416515 42.6411633671774197, -96.7152732864608993 42.6219073671594870, -96.7140592864597721 42.6123023671505408, -96.6366722863876930 42.5507313670931993, -96.6292942863808264 42.5226933670670917, -96.6054672863586319 42.5072363670526912, -96.5847532863393496 42.5182873670629817, -96.5472152863043931 42.5204993670650424, -96.4947012862554772 42.4884593670352047, -96.4393942862039637 42.4892403670359329, -96.3960742861636248 42.4674013670155972, -96.3978902861653211 42.4417933669917460, -96.4176282861836995 42.4147773669665824, -96.4117612861782334 42.3809183669350489, -96.4241752861897936 42.3492793669055843, -96.3897812861577705 42.3287893668864967, -96.3687002861381359 42.2980233668578478, -96.3428812861140784 42.2820813668430020, -96.3326582861045608 42.2603073668227225, -96.3377082861092617 42.2295223667940505, -96.3635122861333002 42.2140423667796370, -96.3521652861227267 42.1681853667369211, -96.2851232860602977 42.1234523666952612, -96.2654832860419987 42.0488973666258303, -96.2387252860170861 42.0284383666067782, -96.2360932860146363 42.0012583665814674, -96.2028422859836638 41.9966153665771387, -96.1852172859672550 41.9806853665622981, -96.1473282859319625 41.9662543665488670, -96.1458702859305987 41.9249073665103538, -96.1599702859437429 41.9041513664910212, -96.1356232859210564 41.8626203664523473, -96.0764172858659151 41.7914693663860817, -96.0993212858872567 41.7529753663502277, -96.0997712858876696 41.7315633663302918, -96.0855572858744296 41.7049873663055379, -96.1222022859085570 41.6949133662961557, -96.1202642859067566 41.6840943662860823, -96.0993062858872378 41.6546803662586882, -96.1113072858984197 41.5990063662068366, -96.0808352858700374 41.5760003661854114, -96.0919362858803794 41.5631453661734369, -96.0858402858746956 41.5375223661495738, -96.0501722858414837 41.5243353661372936, -96.0045922857990348 41.5366633661487725, -95.9939652857891303 41.5281033661408046, -95.9966882857916630 41.5115173661253607, -96.0134512858072782 41.4929943661081069, -96.0068972858011733 41.4819543660978240, -95.9531852857511467 41.4723873660889097, -95.9350652857342823 41.4623813660795975, -95.9400562857389190 41.3948053660166551, -95.9428952857415709 41.3400773659656906, -95.8891072856914803 41.3013893659296585, -95.8975912856993773 41.2868633659161333, -95.9112022857120508 41.3084693659362543, -95.9302302857297775 41.3020563659302837, -95.9109812857118413 41.2252453658587399, -95.9222502857223418 41.2078543658425502, -95.9161002857166096 41.1940633658297060, -95.8591982856636236 41.1805373658171021, -95.8598012856641759 41.1668653658043695, -95.8766852856799119 41.1642023658018985, -95.8582742856627590 41.1091873657506568, -95.8788042856818805 41.0658713657103149, -95.8595392856639421 41.0350023656815637, -95.8608972856652031 41.0026503656514336, -95.8376032856435103 40.9742583656249906, -95.8365412856425252 40.9011083655568655, -95.8343962856405227 40.8703003655281805, -95.8464352856517365 40.8483323655077157, -95.8517902856567190 40.7926003654558116, -95.8766162856798445 40.7304363653979209, -95.7679992855786821 40.6431173653165985, -95.7575462855689494 40.6209043652959068, -95.7674792855782044 40.5890483652662368, -95.7634122855744181 40.5497073652296010, -95.7370362855498485 40.5323733652134592, -95.6920662855079627 40.5241293652057806, -95.6874132855036379 40.5611703652402724, -95.6756932854927129 40.5658353652446237, -95.6629442854808474 40.5587293652380083, -95.6580602854762958 40.5303323652115566, -95.6849702855013646 40.5122053651946743, -95.6953612855110407 40.4853383651696532, -95.6368172854565159 40.3963903650868161, -95.6341852854540662 40.3588003650518061, -95.6162012854373131 40.3464973650403493, -95.6179332854389230 40.3314183650263018, -95.6455532854646435 40.3223463650178502, -95.6468272854658323 40.3091093650055257, -95.5955322854180594 40.3097763650061438, -95.5471372853729974 40.2662153649655750, -95.4768222853075059 40.2268553649289231, -95.4666362852980228 40.2132553649162503, -95.4609522852927199 40.1739953648796870, -95.4224762852568915 40.1317433648403465, -95.3928132852292663 40.1154163648251370, -95.3845422852215563 40.0953623648064621, -95.4037842852394817 40.0803793647925062, -95.4137642852487744 40.0481113647624483, -95.3905322852271382 40.0437503647583952, -95.3712442852091726 40.0287513647444229, -95.3450672851847969 40.0249743647409062, -95.3086972851509273 39.9994073647170936, -95.3297012851704864 39.9925953647107519, -95.7807002855905125 39.9934893647115786, -96.0012532857959258 39.9951593647131389, -96.2405982860188232 39.9945033647125285, -96.4540382862176102 39.9941723647122132, -96.8014202865411306 39.9944763647124972, -96.9082872866406575 39.9961543647140658, -97.3619122870631344 39.9973803647152053, -97.8165892874865790 39.9997293647173962, -97.9295882875918267 39.9984523647162007, -98.2641652879034240 39.9984343647161893, -98.5044792881272286 39.9971293647149722, -98.7206322883285452 39.9984613647162135, -99.0647472886490164 39.9983383647160977, -99.1782012887546784 39.9995773647172541, -99.6278592891734576 40.0029873647204255, -100.1809102896885264 40.0004783647180915, -100.1911112896980285 40.0005853647181908, -100.7350492902046142 39.9991723647168698, -100.7548562902230600 40.0001983647178321, -101.3221482907513860 40.0018213647193406, -101.4073932908307825 40.0010033647185850)), ((-91.1201322812500223 40.7054433653746415, -91.1293032812585579 40.6821893653529827, -91.1626442812896158 40.6563523653289209, -91.2150602813384239 40.6438593653172830, -91.2622112813823492 40.6395873653133037, -91.3757622814880932 40.6034803652796796, -91.4112712815211665 40.5730123652513015, -91.4130262815228036 40.5480343652280411, -91.3822552814941389 40.5285383652098830, -91.3749462814873397 40.5036973651867527, -91.3855512814972144 40.4472943651342263, -91.3729082814854365 40.4030323650929972, -91.3859092814975469 40.3924053650831070, -91.4189682815283362 40.3869193650779934, -91.4487472815560665 40.3719463650640478, -91.4770382815824092 40.3910123650818065, -91.4903142815947774 40.3908063650816160, -91.5003772816041447 40.4051603650949858, -91.5276912816295862 40.4101693650996481, -91.5296072816313711 40.4350863651228565, -91.5388462816399766 40.4412883651286279, -91.5332082816347281 40.4554413651418088, -91.5793832816777353 40.4637603651495539, -91.5860282816839231 40.4845193651688930, -91.6168602817126327 40.5048733651878479, -91.6225362817179274 40.5329033652139543, -91.6920812817826913 40.5516773652314342, -91.6899592817807161 40.5812023652589318, -91.7169762818058700 40.5934353652703237, -91.7417112818289127 40.6097843652855488, -91.9463702820195152 40.6082663652841376, -92.1931742822493732 40.6000883652765197, -92.3615132824061504 40.5995763652760431, -92.6464322826714977 40.5914623652684838, -92.7178152827379733 40.5896673652668198, -93.1009382830947914 40.5843473652618627, -93.3702712833456303 40.5804913652582684, -93.5629102835250421 40.5808133652585710, -93.7863032837330906 40.5784483652563637, -94.0180592839489293 40.5740223652522474, -94.2383922841541306 40.5709663652494044, -94.4852312843840139 40.5742053652524177, -94.6398762845280430 40.5757443652538541, -94.9206162847895030 40.5772183652552201, -95.2174282850659210 40.5818923652595771, -95.3825552852197092 40.5843343652618529, -95.7674792855782044 40.5890483652662368, -95.7575462855689494 40.6209043652959068, -95.7679992855786821 40.6431173653165985, -95.8766162856798445 40.7304363653979209, -95.8517902856567190 40.7926003654558116, -95.8464352856517365 40.8483323655077157, -95.8343962856405227 40.8703003655281805, -95.8365412856425252 40.9011083655568655, -95.8376032856435103 40.9742583656249906, -95.8608972856652031 41.0026503656514336, -95.8595392856639421 41.0350023656815637, -95.8788042856818805 41.0658713657103149, -95.8582742856627590 41.1091873657506568, -95.8766852856799119 41.1642023658018985, -95.8598012856641759 41.1668653658043695, -95.8591982856636236 41.1805373658171021, -95.9161002857166096 41.1940633658297060, -95.9222502857223418 41.2078543658425502, -95.9109812857118413 41.2252453658587399, -95.9302302857297775 41.3020563659302837, -95.9112022857120508 41.3084693659362543, -95.8975912856993773 41.2868633659161333, -95.8891072856914803 41.3013893659296585, -95.9428952857415709 41.3400773659656906, -95.9400562857389190 41.3948053660166551, -95.9350652857342823 41.4623813660795975, -95.9531852857511467 41.4723873660889097, -96.0068972858011733 41.4819543660978240, -96.0134512858072782 41.4929943661081069, -95.9966882857916630 41.5115173661253607, -95.9939652857891303 41.5281033661408046, -96.0045922857990348 41.5366633661487725, -96.0501722858414837 41.5243353661372936, -96.0858402858746956 41.5375223661495738, -96.0919362858803794 41.5631453661734369, -96.0808352858700374 41.5760003661854114, -96.1113072858984197 41.5990063662068366, -96.0993062858872378 41.6546803662586882, -96.1202642859067566 41.6840943662860823, -96.1222022859085570 41.6949133662961557, -96.0855572858744296 41.7049873663055379, -96.0997712858876696 41.7315633663302918, -96.0993212858872567 41.7529753663502277, -96.0764172858659151 41.7914693663860817, -96.1356232859210564 41.8626203664523473, -96.1599702859437429 41.9041513664910212, -96.1458702859305987 41.9249073665103538, -96.1473282859319625 41.9662543665488670, -96.1852172859672550 41.9806853665622981, -96.2028422859836638 41.9966153665771387, -96.2360932860146363 42.0012583665814674, -96.2387252860170861 42.0284383666067782, -96.2654832860419987 42.0488973666258303, -96.2851232860602977 42.1234523666952612, -96.3521652861227267 42.1681853667369211, -96.3635122861333002 42.2140423667796370, -96.3377082861092617 42.2295223667940505, -96.3326582861045608 42.2603073668227225, -96.3428812861140784 42.2820813668430020, -96.3687002861381359 42.2980233668578478, -96.3897812861577705 42.3287893668864967, -96.4241752861897936 42.3492793669055843, -96.4117612861782334 42.3809183669350489, -96.4176282861836995 42.4147773669665824, -96.3978902861653211 42.4417933669917460, -96.3960742861636248 42.4674013670155972, -96.4393942862039637 42.4892403670359329, -96.4802432862420147 42.5171303670619096, -96.4893372862504890 42.5640283671055784, -96.5009422862612922 42.5738853671147623, -96.4884982862497083 42.5804803671209058, -96.5128442862723688 42.6297553671667941, -96.5411652862987495 42.6624053671972092, -96.5630392863191247 42.6685133672028911, -96.6265402863782583 42.7083543672399983, -96.6407092863914556 42.7486033672774823, -96.6329802863842673 42.7768353673037751, -96.6008752863543663 42.7995583673249342, -96.5876452863420383 42.8353813673583019, -96.5731262863285167 42.8343473673573385, -96.5562112863127595 42.8466603673688056, -96.5375112862953557 42.8969063674155962, -96.5442632863016428 42.9138663674313960, -96.5149352862743228 42.9523823674672656, -96.5171482862763810 42.9864583674989973, -96.4990202862594941 43.0120503675228321, -96.5200102862790459 43.0515083675595847, -96.4795732862413900 43.0618843675692489, -96.4620942862251098 43.0755823675820011, -96.4608052862239163 43.0878723675934481, -96.4515052862152515 43.1263083676292496, -96.4731142862353721 43.2090823677063369, -96.4872452862485375 43.2179093677145545, -96.5586052863150002 43.2254893677216216, -96.5669912863228035 43.2396333677347897, -96.5595672863158967 43.2532633677474792, -96.5707222863262729 43.2636123677571192, -96.5791312863341034 43.2900743677817701, -96.5405632862981946 43.3076593677981450, -96.5228942862817405 43.3569663678440662, -96.5250532862837503 43.3842253678694476, -96.5577082863141527 43.4007273678848193, -96.5891132863434052 43.4355393679172437, -96.5837962863384547 43.4819203679604414, -96.5983152863519763 43.4998493679771343, -96.4604542862235803 43.4997183679770103, -96.0610392858516065 43.4985333679759094, -95.8669122856708071 43.4989443679762928, -95.4647752852962839 43.4995413679768461, -95.3965582852327572 43.5003343679775867, -94.9204642847893609 43.4993713679766927, -94.8598392847328995 43.5000303679773026, -94.4552382843560849 43.4981023679755054, -94.2467872841619396 43.4989483679762969, -93.9739502839078398 43.5002983679775497, -93.6536992836095834 43.5007623679779840, -93.5008302834672236 43.5004883679777308, -93.0543802830514295 43.5014573679786309, -93.0272112830261335 43.5012783679784647, -92.5580082825891424 43.5002593679775202, -92.4531692824915154 43.4994623679767756, -92.0775322821416751 43.4991533679764899, -91.7303662818183483 43.4995713679768770, -91.6110992817072685 43.5006263679778584, -91.2235662813463506 43.5008083679780242, -91.2359032813578352 43.4646843679443862, -91.2109162813345762 43.4240513679065430, -91.1982432813227746 43.3705133678566810, -91.1770482813030299 43.3539463678412531, -91.0784982812112531 43.3132973678033935, -91.0664282812000039 43.2806833677730225, -91.0690522812024454 43.2578983677517996, -91.1613542812884106 43.1475763676490516, -91.1685712812951294 43.0828883675888079, -91.1597522812869130 43.0811823675872176, -91.1522142812798961 43.0013163675128425, -91.1391212812677054 42.9258933674425975, -91.0934282812251439 42.8714403673918838, -91.0820302812145428 42.7833653673098553, -91.0661682811997650 42.7449133672740444, -90.9991822811373794 42.7070583672387869, -90.9194092810630821 42.6806773672142228, -90.8925452810380676 42.6782403672119557, -90.7456102809012179 42.6570013671921728, -90.6947912808538916 42.6379283671744105, -90.6643802808255685 42.5713913671124402, -90.6392192808021377 42.5557143670978419, -90.6257072807895554 42.5285623670725528, -90.6384562808014209 42.5093633670546751, -90.6518992808139501 42.4947003670410197, -90.6484732808107481 42.4756473670232708, -90.6059552807711555 42.4605643670092263, -90.5637112807318090 42.4218433669731638, -90.4911712806642612 42.3887913669423853, -90.4417252806182006 42.3600833669156458, -90.4278092806052456 42.3406453668975402, -90.4181122805962190 42.2639393668261079, -90.4073012805861396 42.2426613668062885, -90.3678582805494131 42.2102263667760838, -90.3237302805083146 42.1973373667640743, -90.2310632804220063 42.1597413667290652, -90.1917022803853570 42.1227103666945766, -90.1762142803709281 42.1205243666925355, -90.1667762803621429 42.1037673666769336, -90.1682262803634842 42.0610663666371636, -90.1506632803471319 42.0334533666114467, -90.1427962803398088 41.9839893665653818, -90.1546452803508345 41.9308023665158487, -90.1959652803893164 41.8061673663997695, -90.2554382804447073 41.7817693663770484, -90.3050162804908894 41.7564973663535142, -90.3261572805105715 41.7227683663221001, -90.3412622805246457 41.6491223662535077, -90.3394762805229732 41.6028313662103955, -90.3484942805313835 41.5868823661955460, -90.4231352806008886 41.5673053661773082, -90.4350982806120385 41.5436123661552443, -90.4551262806306795 41.5275793661403156, -90.5409752807106400 41.5260033661388519, -90.6008382807663963 41.5096183661235898, -90.6589292808204874 41.4623503660795620, -90.7083542808665300 41.4500933660681454, -90.7800422809332872 41.4498523660679297, -90.8442842809931221 41.4446523660630817, -90.9498002810913846 41.4212633660413019, -91.0008422811389295 41.4311123660504705, -91.0276372811638765 41.4235363660434217, -91.0559352811902301 41.4014073660228092, -91.0734292812065291 41.3349253659608920, -91.1024962812335986 41.2678483658984163, -91.1016722812328226 41.2315523658646157, -91.0564662811907226 41.1762903658131521, -91.0184022811552751 41.1658573658034328, -90.9904852811292812 41.1444043657834584, -90.9579302810989532 41.1043933657461906, -90.9547942810960421 41.0703973657145269, -90.9608512811016823 40.9505413656029020, -90.9834192811226927 40.9239653655781552, -91.0493532811840964 40.8796233655368582, -91.0890502812210769 40.8337673654941540, -91.0928952812246564 40.7615873654269336, -91.1201322812500223 40.7054433653746415)))',
        )
        aggregate = forms.ChoiceField(
            choices=CHOICES_AGGREGATE,
            initial='true',
        )
        spatial_op = forms.ChoiceField(
            choices=CHOICES_SOP,
            initial='intersects',
            label='Spatial Operation',
        )
        extension = forms.ChoiceField(
            choices=CHOICES_EXT,
            label='Format',
        )
        stat = forms.MultipleChoiceField(
            choices=OcgStatFunction.get_potentials(),
            widget=forms.CheckboxSelectMultiple,
            label='Aggregate Statistic(s)',
            required=False
        )
        grouping = forms.MultipleChoiceField(
            choices=[('day','Day'),('month','Month'),('year','Year')],
            widget=forms.CheckboxSelectMultiple,
            label='Grouping Interval(s)',
            required=False
        )
        
        def clean(self):
            if self.is_valid():
                ## test that dates are not switched or equal
                if self.cleaned_data['drange_lower'] >= self.cleaned_data['drange_upper']:
                    raise(ValidationError('Date range values equal or switched.'))
            return(self.cleaned_data)
        
    return(SpatialQueryForm)

def display_spatial_query(request):
    ## get the dynamically generated form class
    SpatialQueryForm = get_SpatialQueryForm(request.ocg.simulation_output)
    ## process the request
    if request.method == 'POST': # If the form has been submitted...
        form = SpatialQueryForm(request.POST) # A form bound to the POST data
        if form.is_valid(): # All validation rules pass
            ## merge keyword arguments for url string
            form.cleaned_data.update(dict(archive=request.ocg.archive.urlslug,
                                          climate_model=request.ocg.climate_model.urlslug,
                                          run=request.ocg.run,
                                          variable=request.ocg.variable.urlslug,
                                          scenario=request.ocg.scenario.urlslug))
            ## fill in the URL string
            url = ('/api'
                   '/archive/{archive}/model'
                   '/{climate_model}/scenario/{scenario}'
                   '/run/{run}'
                   '/temporal/{drange_lower}+{drange_upper}'
                   '/spatial/{spatial_op}+{wkt_extent}'
                   '/aggregate/{aggregate}'
                   '/variable/{variable}.{extension}').format(**form.cleaned_data)
            ## add query string parms
            query = {}
            for parm in ['stat','grouping']:
                if form.cleaned_data.get(parm):
                    query.update({parm:'+'.join(form.cleaned_data[parm])})
            if query:
                base = []
                for key,value in query.iteritems():
                    base.append(key+'='+value)
                url = url + '?' + '&'.join(base)
            print(url)
            return HttpResponseRedirect(url) # Redirect after POST
    else:
        form = SpatialQueryForm() # An unbound form
        
    return render_to_response('query.html',
                              {'form': form, 'request': request},
                              context_instance=RequestContext(request))

## SHAPEFILE UPLOAD ------------------------------------------------------------

def validate_zipfile(value):
    if not os.path.splitext(value.name)[1] in ['.zip','.kml','.kmz']:
        raise(ValidationError("File extension not '.zip or .kml or .kmz'"))


class UploadShapefileForm(forms.Form):
#    uid = forms.CharField(max_length=50,min_length=1,initial='foo',label='UID')

    filefld = forms.FileField(
        label='Zipped Shapefile or KML File',
        validators=[validate_zipfile],
    )
    code = forms.CharField(
        label='AOI Code',
        help_text='Code by which a user refers to an AOI.'
    )
    uid_field = forms.CharField(
        label='UID Field',
        required=False,
        help_text='This is used to extract a unique identifier from your uploaded data.'
    )
    
    def clean_code(self):
        import re
        
        data = self.cleaned_data['code']
        if re.match('^[A-Za-z0-9_]+$', data) is None:
            raise forms.ValidationError(
                'The AOI code provided is invalid. '
                'Use only letters, numbers, and the underscore character.'
            )
        
        # check if the code has already been used
        if len(UserGeometryMetadata.objects.filter(code=data)) > 0:
            raise forms.ValidationError(
                'The AOI code provided is already being used. '
                'Please provide a different code.'
            )
        
        # Always return the cleaned data, whether you have changed it or
        # not.
        return data
    

@transaction.commit_on_success
def display_shpupload(request):
    if request.method == 'POST':
        form = UploadShapefileForm(request.POST,request.FILES)
        if form.is_valid():
            ## write the file to disk and extract WKT
            wkt = handle_uploaded_file(
                request.FILES['filefld'],
                form.cleaned_data['uid_field'],
            )
            
            ## loop through the dictionary list and store the data. first, create
            ## the metadata object.
            meta = models.UserGeometryMetadata(code=form.cleaned_data['code'],
                                               uid_field=form.cleaned_data['uid_field'])
            meta.save()
            ## next insert the geometries
            for feat in wkt:
                geom = GEOSGeometry(feat['geom'],srid=4326)
                if isinstance(geom,Polygon):
                    geom = MultiPolygon([geom])
                ## extract the user-provided unique identifier if passed
                obj = models.UserGeometryData(user_meta=meta,
                                              gid=feat.get(form.cleaned_data['uid_field']),
                                              geom=geom)
                obj.save()
            
            ## return a success message to the user
            # TODO: redirect to a page listing the AOIs
#            return(HttpResponse((
#                'Upload successful. '
#                'Your geometry code is: <b>{0}</b>').format(obj.code)
#            ))
            return redirect('/api/aois/{0}.html'.format(meta.code))
    else:
        form = UploadShapefileForm()
    return(render_to_response('shpupload.html', {'form': form}))

def handle_uploaded_file(filename,uid_field=None):
    
    if filename.content_type == 'application/zip':
        return handle_uploaded_shapefile(filename,uid_field)
    elif filename.content_type == 'application/vnd.google-earth.kml+xml':
        return handle_uploaded_kmlfile(filename,uid_field)
    else:
        # TODO: handle bad file types
        pass
    
def handle_uploaded_shapefile(filename,uid_field=None):
    
    path = get_temp_path(nest=True,suffix='.zip')
    dir = os.path.split(path)[0]
    ## write the data to file
    with open(path,'wb+') as dest:
        for chunk in filename.chunks():
            dest.write(chunk)
    ## unzip the file
    zip = zipfile.ZipFile(path,'r')
    try:
        zip.extractall(os.path.split(path)[0])
    finally:
        zip.close()
    ## get the shapefile path
    for f in os.listdir(dir):
        if f.endswith('.shp'):
            break
    ## extract the wkt
    wkt_data = get_shp_as_multi(os.path.join(dir,f),uid_field=uid_field)
    return(wkt_data)


def handle_uploaded_kmlfile(filename,objectid):
    from pykml import parser
    from pykml.util import to_wkt_list
    
    # check if the file is too large
    if filename.size >= filename.DEFAULT_CHUNK_SIZE:
        raise IOError
    # parse the incoming file
    doc = parser.fromstring(filename.read())
    # look for geometries
    wkt_list = to_wkt_list(doc)
    
    return(wkt_list)
