import sys
import os
import hashlib
import argparse
import logging
import requests
import json
import time



def format_report(result,filename): 
    scans = result.get("scans") 
    fn = filename[-44:-4]
    f = file('/Users/GaoSir/Desktop/temp/'+fn+".report", "w") #filename is the sample file name 
    scan_list = [] 
    for k,v in scans.items(): 
        if v['detected'] == True: 
            scan_list.append("%s: %s" % (k, v['result'])) 
        else: 
            scan_list.append("%s: None" % k) 
    f.write('\n'.join(scan_list)) 
    f.write("\nSHA256: %s\n" % result['sha256']) 
    f.write("MD5: %s\n" % result['md5']) 
    f.write("Detection ratio: %s/%s\n" % (result['positives'], result['total'])) 
    f.write("Analysis date: %s\n" % (result['scan_date'])) 
    f.write("URL: %s\n" % result['permalink']) 
    f.close() 

 
def list_all_files(path):
    """
    List all file paths

    @param path: if it is a path, just return, if dir, return paths of files in it

    Subdirectories not listed
    No recursive search
    """
    assert os.path.isfile(path) or os.path.isdir(path)
    if os.path.isfile(path):
        return [path]
    else:
        return filter(os.path.isfile, map(lambda x: '/'.join([os.path.abspath(path), x]), os.listdir(path)))

def list_dir(path):
    file_list = []
    files = os.listdir(path)
    for fi in files:
      fi_d = os.path.join(path,fi)            
      if os.path.isdir(fi_d):
        file_list.extend(list_dir(fi_d))                  
      else:
        filename =  os.path.join(path,fi_d)
        file_list.append(filename)
    return file_list


def sha256sum(filename):
    """
    Efficient sha256 checksum realization

    Take in 8192 bytes each time
    The block size of sha256 is 512 bytes
    """
    with open(filename, 'rb') as f:
        m = hashlib.sha256()
        while True:
            data = f.read(8192)
            if not data:
                break
            m.update(data)
        return m.hexdigest()


class VirusTotal(object):
    def __init__(self):
        self.apikey = "fa08f258aeedc03a2eb03d6b7961a5c6469619918d53360ceeaba50477502514"
        self.URL_BASE = "https://www.virustotal.com/vtapi/v2/"
        self.HTTP_OK = 200

        # whether the API_KEY is a public API. limited to 4 per min if so.
        self.is_public_api = True
        # whether a retrieval request is sent recently
        self.has_sent_retrieve_req = False
        # if needed (public API), sleep this amount of time between requests
        self.PUBLIC_API_SLEEP_TIME = 20

        self.logger = logging.getLogger("virt-log")
        self.logger.setLevel(logging.INFO)
        self.scrlog = logging.StreamHandler()
        self.scrlog.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        self.logger.addHandler(self.scrlog)
        self.is_verboselog = False

    def send_files(self, filenames):
        """
        Send files to scan
        
        @param filenames: list of target files
        """
        url = self.URL_BASE + "file/scan"
        attr = {"apikey": self.apikey}

        for filename in filenames:
            files = {"file": open(filename, 'rb')}
            res = requests.post(url, data=attr, files=files)

            if res.status_code == self.HTTP_OK:
                resmap = json.loads(res.text)
                if not self.is_verboselog:
                    self.logger.info("sent: %s, HTTP: %d, response_code: %d, scan_id: %s",
                            os.path.basename(filename), res.status_code, resmap["response_code"], resmap["scan_id"])
                else:
                    self.logger.info("sent: %s, HTTP: %d, content: %s", os.path.basename(filename), res.status_code, res.text)
            else:
                self.logger.warning("sent: %s, HTTP: %d", os.path.basename(filename), res.status_code)

    def retrieve_files_reports(self, filenames):
        for filename in filenames:
            res = self.retrieve_report(sha256sum(filename))
            if res.status_code == self.HTTP_OK:
                resmap = json.loads(res.text)
                if not self.is_verboselog:
                    self.logger.info("retrieve report: %s, HTTP: %d, response_code: %d, scan_date: %s, positives/total: %d/%d",
                            os.path.basename(filename), res.status_code, resmap["response_code"], resmap["scan_date"], resmap["positives"], resmap["total"])
                    format_report(resmap,filename)
                else:
                    self.logger.info("retrieve report: %s, HTTP: %d, content: %s", os.path.basename(filename), res.status_code, res.text)
            else:
                self.logger.warning("retrieve report: %s, HTTP: %d", os.path.basename(filename), res.status_code)

    def retrieve_from_meta(self, filename):
        """
        Retrieve Report for checksums in the metafile

        @param filename: metafile, each line is a checksum, best use sha256
        """
        with open(filename) as f:
            for line in f:
                checksum = line.strip()
                res = self.retrieve_report(checksum)

                if res.status_code == self.HTTP_OK:
                    resmap = json.loads(res.text)
                    if not self.is_verboselog:
                        self.logger.info("retrieve report: %s, HTTP: %d, response_code: %d, scan_date: %s, positives/total: %d/%d",
                                checksum, res.status_code, resmap["response_code"], resmap["scan_date"], resmap["positives"], resmap["total"])
                    else:
                        self.logger.info("retrieve report: %s, HTTP: %d, content: %s", os.path.basename(filename), res.status_code, res.text)
                else:
                    self.logger.warning("retrieve report: %s, HTTP: %d", checksum, res.status_code)

    def retrieve_report(self, chksum):
        """
        Retrieve Report for the file checksum

        4 retrieval per min if only public API used

        @param chksum: sha256sum of the target file
        """
        if self.has_sent_retrieve_req and self.is_public_api:
            time.sleep(self.PUBLIC_API_SLEEP_TIME)

        url = self.URL_BASE + "file/report"
        params = {"apikey": self.apikey, "resource": chksum}
        res = requests.post(url, data=params)
        self.has_sent_retrieve_req = True
        return res



if __name__ == "__main__":
    vt = VirusTotal()

    parser = argparse.ArgumentParser(description='Virustotal File Scan')
    parser.add_argument("-p", "--private", help="the API key belongs to a private API service", action="store_true")
    parser.add_argument("-v", "--verbose", help="print verbose log (everything in response)", action="store_true")
    parser.add_argument("-s", "--send", help="send a file or a directory of files to scan", metavar="PATH")
    parser.add_argument("-r", "--retrieve", help="retrieve reports on a file or a directory of files", metavar="PATH")
    parser.add_argument("-m", "--retrievefrommeta", help="retrieve reports based on checksums in a metafile (one sha256 checksum for each line)", metavar="METAFILE")
    parser.add_argument("-l", "--log", help="log actions and responses in file", metavar="LOGFILE")
    args = parser.parse_args()

    if args.log:
        filelog = logging.FileHandler(args.log)
        filelog.setFormatter(logging.Formatter("[%(asctime)s %(levelname)s] %(message)s", datefmt="%m/%d/%Y %I:%M:%S"))
        vt.logger.addHandler(filelog)

    if args.private:
        vt.is_public_api = False

    if args.verbose:
        vt.is_verboselog = True

    # system init end, start to perform operations
    api_comments = {True: 'Public', False: 'Private'}
    vt.logger.info("API KEY loaded. %s API used.", api_comments[vt.is_public_api])

    if args.send:
        vt.send_files(list_all_files(args.send))

    if args.retrieve:
        vt.retrieve_files_reports(list_all_files(args.retrieve))

    if args.retrievefrommeta:
        vt.retrieve_from_meta(args.retrievefrommeta)
