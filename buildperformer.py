import time
import performer

if __name__ == "__main__":

    results = []
    performs = (
        "scripts/buildperformance/get-small.xml",
        "scripts/buildperformance/get-large.xml",
        "scripts/buildperformance/put-small.xml",
        "scripts/buildperformance/put-large.xml",
    )
    
    for item in performs:
        pinfo, result = performer.runIt(item)
        results.append((item[item.rfind("/")+1:item.rfind(".")], result[0][0], result[0][1], result[0][2]))
  
    print time.ctime(),
    for result in results:
        print "\t%s\t%.3f\t%.3f\t%.3f" % (result[0], result[1], result[2], result[3],),
    print ""
