import os
import sys

from pdf2image import (
    convert_from_path,
    pdfinfo_from_path,
)
from pdf2image.exceptions import (
    PDFInfoNotInstalledError,
    PDFPageCountError,
    PDFSyntaxError,
)
from PIL import Image
import uuid
import mimetypes
from urllib.parse import unquote_plus
import pdfplumber
import threading
import re
import json
import platform
from bidi.algorithm import get_display

is_dev_local = platform.system() == "Darwin"

if not is_dev_local:
    import boto3

    s3Client = boto3.client('s3')
    from boto3.s3.transfer import TransferConfig

    KB = 1024
    MB = KB * KB
    config = TransferConfig(
        multipart_threshold=1 * MB,
        max_concurrency=5,
        multipart_chunksize=1 * MB,
        max_io_queue=10000,
        io_chunksize=1 * MB,
        use_threads=True
    )

Image.MAX_IMAGE_PIXELS = None


def pdf_extract_words(file, bucketKey):
    global json_words_ocr
    pages = []
    try:
        print('file:', file)
        with pdfplumber.open(file, strict_metadata=True) as pdf:
            print('----Metadata:------')
            print(pdf.metadata)
            # print('----pdf.pages:------')
            # print(len(pdf.pages))
            is_heb_flow_doc = False
            # if ('Title' in pdf.metadata):
            #     is_heb_flow_doc = any("\u0590" <= c <= "\u05EA" for c in pdf.metadata['Title'])
            # print('is_heb_flow_doc: ', is_heb_flow_doc)
            lines = []
            with open('hebrew_vocabulary_list.txt') as f:
                lines = f.readlines()

            for i in range(0, len(pdf.pages)):
                obj = {
                    'textAnnotations': [
                        # {
                        #     'locale': 'iw',
                        #     'description': '',
                        #     'boundingPoly': {
                        #         'vertices': []
                        #     }
                        # }
                    ]
                }
                # width = float(pdf.pages[i].width)
                # height = float(pdf.pages[i].height)
                # print(width, height)

                extract_words = pdf.pages[i].extract_words(x_tolerance=1,
                                                           y_tolerance=1,
                                                           keep_blank_chars=False,
                                                           # split_at_punctuation='\s',
                                                           use_text_flow=True,
                                                           horizontal_ltr=True,
                                                           vertical_ttb=True,
                                                           extra_attrs=[
                                                               "fontname"
                                                           ])
                # im = pdf.pages[i].to_image(resolution=150)
                # aaa = im.draw_rects(extract_words)
                # cv2.imwrite('aaa.jpg', aaa)

                extract_words_src = pdf.pages[i].extract_words(x_tolerance=1,
                                                               y_tolerance=1,
                                                               # split_at_punctuation='\s',
                                                               keep_blank_chars=False,
                                                               use_text_flow=False,
                                                               horizontal_ltr=False,
                                                               vertical_ttb=True,
                                                               extra_attrs=[
                                                                   "fontname"
                                                               ])
                for word in extract_words_src:
                    obj["textAnnotations"].append({
                        "description": None,
                        "locale": "he",
                        "boundingPoly": {
                            "vertices": [{
                                "x": int(word['x0']),
                                "y": int(word['top'])
                            }, {
                                "x": int(word['x1']),
                                "y": int(word['top'])
                            }, {
                                "x": int(word['x1']),
                                "y": int(word['bottom'])
                            }, {
                                "x": int(word['x0']),
                                "y": int(word['bottom'])
                            }]
                        }
                    })
                # print(extract_words_src)

                words_heb_straight = 0
                words_heb_reverse = 0
                for word in extract_words:
                    for x in word['text'].split('\n'):
                        # print(x)
                        if x != '':
                            is_heb = False
                            abc = re.findall(r'\(cid\:\d+\)', x)
                            if len(abc) > 0:
                                # print('is cid!!!!')
                                for cid in abc:
                                    try:
                                        cidx_int = int(re.findall(r'\(cid\:(\d+)\)', cid)[0])
                                        if cidx_int > 672:
                                            is_heb = True
                                        x = x.replace(cid, cidToChar(cidx_int))
                                    except:
                                        pass
                            else:
                                is_heb = (any("\u0590" <= c <= "\u05EA" for c in x))

                            # print("is_heb word: ", is_heb, x)

                            if is_heb:
                                is_straight_hebrew_local = False
                                is_reverse_hebrew_local = False

                                for line in lines:
                                    line = line.replace('\\n', '').replace('\\t', '').replace('\n', '').replace('\t',
                                                                                                                '')
                                    if x.casefold() == line.casefold():
                                        is_straight_hebrew_local = True
                                        # print('line', line)
                                        break

                                    if repr(x).strip("'")[::-1].casefold() == line.casefold():
                                        is_reverse_hebrew_local = True
                                        # print('line', line)
                                        break

                                if is_straight_hebrew_local:
                                    words_heb_straight += 1
                                if is_reverse_hebrew_local:
                                    words_heb_reverse += 1

                        # print("word['text'] After!!", word['text'])
                    # print(words[len(words) - 1]['text'])
                # print('words_heb_straight', words_heb_straight)
                # print('words_heb_reverse', words_heb_reverse)

                additionalWithoutAdjustingPos = []
                for word in extract_words:
                    # print("word['text'] before", word['text'])
                    for x in word['text'].split('\n'):
                        if x != '':
                            is_heb = False
                            abc = re.findall(r'\(cid\:\d+\)', x)
                            if len(abc) > 0:
                                # print('is cid!!!!')
                                for cid in abc:
                                    try:
                                        cidx_int = int(re.findall(r'\(cid\:(\d+)\)', cid)[0])
                                        if cidx_int > 672:
                                            is_heb = True
                                        x = x.replace(cid, cidToChar(cidx_int))
                                    except:
                                        pass
                            else:
                                is_heb = (any("\u0590" <= c <= "\u05EA" for c in x))

                            # print("is_heb word: ", is_heb, x)

                            if is_heb:
                                is_straight_hebrew = False
                                is_reverse_hebrew = False

                                for line in lines:
                                    line = line.replace('\\n', '').replace('\\t', '').replace('\n', '').replace('\t',
                                                                                                                '')
                                    if x.casefold() == line.casefold():
                                        is_straight_hebrew = True
                                        # print('line', line)
                                        break

                                    if repr(x).strip("'")[::-1].casefold() == line.casefold():
                                        is_reverse_hebrew = True
                                        # print('line', line)

                                if is_straight_hebrew:
                                    word['text'] = repr(x).strip("'")
                                else:
                                    if words_heb_straight > words_heb_reverse and not is_reverse_hebrew:
                                        word['text'] = repr(x).strip("'")
                                    else:
                                        word['text'] = get_display(repr(x).strip("'"))

                            else:
                                word['text'] = repr(x).strip("'")

                            # print("word['text'] After!!", word['text'])

                    languageCode = "en"
                    if is_heb:
                        languageCode = "he"

                    boundingPoly = {
                        "vertices": [{
                            "x": int(word['x0']),
                            "y": int(word['top'])
                        }, {
                            "x": int(word['x1']),
                            "y": int(word['top'])
                        }, {
                            "x": int(word['x1']),
                            "y": int(word['bottom'])
                        }, {
                            "x": int(word['x0']),
                            "y": int(word['bottom'])
                        }]
                    }
                    get_index_match = next(
                        (i for i, d in enumerate(obj["textAnnotations"]) if
                         str(d['boundingPoly']) == str(boundingPoly)),
                        None)
                    if get_index_match is not None:
                        obj["textAnnotations"][get_index_match]['description'] = word['text']
                        obj["textAnnotations"][get_index_match]['locale'] = languageCode
                    else:
                        additionalWithoutAdjustingPos.append({
                            "description": word['text'],
                            "locale": languageCode,
                            "boundingPoly": boundingPoly
                        })
                    # print(word['text'])
                    # print('get_index_match', get_index_match, obj["textAnnotations"][get_index_match]['description'], word['text'])
                    # print(words[len(words) - 1]['text'])

                if obj and obj["textAnnotations"] and len(obj["textAnnotations"]) > 0:
                    obj["textAnnotations"] = list(
                        filter(lambda x_val: x_val["description"] != None, obj["textAnnotations"]))

                    # print('obj: ', obj)
                    # print('additionalWithoutAdjustingPos: ', additionalWithoutAdjustingPos)
                obj["textAnnotations"] = obj["textAnnotations"] + additionalWithoutAdjustingPos
                # print('textAnnotations: ', obj["textAnnotations"])
                # d = sorted(obj["textAnnotations"], key=lambda k: [k['boundingPoly']['vertices'][0]['y'],
                #                                                   -k['boundingPoly']['vertices'][1]['x']])
                # print(d)
                # new_arr = []
                # for index, line in enumerate(d):
                #     print(line)
                    # if len(d) > index + 1:
                    #     diff_y = abs(
                    #         d[index + 1]['boundingPoly']['vertices'][0]['y'] - line['boundingPoly']['vertices'][0]['y'])
                    #     if diff_y < 10:
                    #         diff_x = abs(
                    #             d[index + 1]['boundingPoly']['vertices'][0]['x'] - line['boundingPoly']['vertices'][0][
                    #                 'x'])
                    #         if diff_x < 10:
                    #             print('y: ', line['boundingPoly']['vertices'][0]['y'], 'x: ',
                    #                   line['boundingPoly']['vertices'][0]['x'],
                    #                   line['description'], d[index + 1]['description'])
                    #             print('diff_y: ', diff_y)
                    #             print('diff_x: : ', diff_x)
                    #         diff_x_2 = abs(
                    #             d[index + 1]['boundingPoly']['vertices'][1]['x'] - line['boundingPoly']['vertices'][1][
                    #                 'x'])
                    #         if diff_x_2 < 10:
                    #             print('y: ', line['boundingPoly']['vertices'][0]['y'], 'x: ',
                    #                   line['boundingPoly']['vertices'][0]['x'],
                    #                   line['description'], d[index + 1]['description'])
                    #             print('diff_y: ', diff_y)
                    #             print('diff_x_2: : ', diff_x_2)

                pages.append(obj)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback_details = {
            'filename': exc_traceback.tb_frame.f_code.co_filename,
            'lineno': exc_traceback.tb_lineno,
            'function_name': exc_traceback.tb_frame.f_code.co_name,
            'type': exc_type.__name__,
            'message': str(exc_value)
        }
        del (exc_type, exc_value, exc_traceback)
        print('traceback_details: ', str(traceback_details))
    json_words_ocr = pages


def convert_pdf(file_path, bucketKey, set_dpi):
    global output_path
    output_path = []
    try:
        info = pdfinfo_from_path(file_path)
        if set_dpi == True:
            output_path = convert_from_path(file_path,
                                            output_folder='/tmp',
                                            fmt="jpeg",
                                            jpegopt={"quality": 100, "progressive": True, "optimize": True},
                                            size=(None, 3508),
                                            dpi=300,
                                            paths_only=True)
            if info['Pages'] > len(output_path):
                print('Error found on any page')
                output_path = convert_from_path(file_path,
                                                output_folder='/tmp',
                                                fmt="jpeg",
                                                jpegopt={"quality": 100, "progressive": True, "optimize": True},
                                                dpi=300,
                                                paths_only=True)
        else:
            output_path = convert_from_path(file_path,
                                            output_folder='/tmp',
                                            fmt="jpeg",
                                            jpegopt={"quality": 100, "progressive": True, "optimize": True},
                                            dpi=72,
                                            paths_only=True)

    except PDFInfoNotInstalledError as e_data:
        print('e_data', e_data)
    except PDFPageCountError as e_data1:
        print('e_data1', e_data1)
    except PDFSyntaxError as e_data2:
        print('e_data2', e_data2)
    except Exception as general_error:
        print(general_error)
        print("Something went wrong")
    finally:
        print("finally convert_pdf")


def cidToChar(cidx):
    # if cidx_int == 3:
    #     return chr(32)
    # elif cidx_int == 5:
    #     return chr(34)
    # elif cidx_int == 29:
    #     return chr(58)
    if cidx > 97:
        return chr(cidx + 816)
    else:
        return chr(cidx + 29)
    # int_of_char = int(re.findall(r'\(cid\:(\d+)\)', cidx)[0]) + 816
    # return next(y for y in chars if y["code"] == int_of_char)['txt']


def convert_tiff(file_path, bucketKey):
    temp_images = []
    try:
        images = Image.open(file_path)
        for i in range(images.n_frames):
            images.seek(i)
            images.thumbnail(images.size)
            out = images.convert("RGB")
            image_path = f'/tmp/{bucketKey}_{i}.jpg'
            out.save(image_path, "JPEG", quality=100)
            temp_images.append(image_path)
        return temp_images
    except Exception as e:
        print(e)
        return temp_images


def lambda_handler(event, context):
    bucketName = event['bucket']
    bucketKey = unquote_plus(event['key'], encoding='utf-8')
    if not is_dev_local:
        download_path = '/tmp/{}_{}'.format(uuid.uuid4(), bucketKey)
        s3Client.download_file(bucketName, bucketKey, download_path)
    else:
        download_path = event['download_path']

    global output_path
    output_path = []
    names_images_uploaded = []
    global json_words_ocr
    json_words_ocr = []
    bucketKeyClean = ""

    try:
        try:
            mime_type = mimetypes.guess_type(download_path)[0]
            print("The mimetypes is: ", mime_type)
        except Exception as mime_err:
            print(mime_err)
            raise mime_err

        bucketKeyClean = bucketKey.replace(".pdf", "").replace(".", "")
        if mime_type == 'application/pdf':
            # pdf_extract_words_thread = threading.Thread(target=pdf_extract_words, args=(download_path, bucketKeyClean))
            # pdf_extract_words_thread.setDaemon(True)
            # pdf_extract_words_thread.start()
            # pdf_extract_words_thread.join()

            set_dpi = True
            if json_words_ocr and len(json_words_ocr) > 0 and json_words_ocr[0]["textAnnotations"] and len(
                    json_words_ocr[0]["textAnnotations"]) > 1:
                set_dpi = False

            convert_pdf_main_thread = threading.Thread(target=convert_pdf,
                                                       args=(download_path, bucketKeyClean, set_dpi))
            convert_pdf_main_thread.setDaemon(True)
            convert_pdf_main_thread.start()
            convert_pdf_main_thread.join()
        if mime_type == 'image/tiff' or mime_type == 'image/bmp':
            output_path = convert_tiff(download_path, bucketKeyClean)
    except Exception as e:
        print(e)
        raise e
    finally:
        if not is_dev_local:
            if os.path.exists(download_path):
                os.remove(download_path)
                print('The files removed download_path !')

    try:
        for index in range(len(output_path)):
            if not is_dev_local:
                s3Client.upload_file(output_path[index], bucketName, f'{bucketKeyClean}_{index}.jpg',
                                     ExtraArgs={"ContentType": "image/jpeg"},
                                     Config=config)

            output_obj = {'bucketName': bucketName, 'bucketKey': f'{bucketKeyClean}_{index}.jpg'}
            if mime_type == 'application/pdf':
                if json_words_ocr and len(json_words_ocr) > 0 and json_words_ocr[index]["textAnnotations"] and len(
                        json_words_ocr[index]["textAnnotations"]) > 1:
                    output_obj["jsonKey"] = f'{bucketKeyClean}_{index}.json'
                    with open(f'/tmp/{output_obj["jsonKey"]}', 'w') as outfile:
                        json.dump(json_words_ocr[index], outfile)
                    if not is_dev_local:
                        s3Client.upload_file(f'/tmp/{output_obj["jsonKey"]}', bucketName, output_obj["jsonKey"],
                                             ExtraArgs={"ContentType": "application/json"},
                                             Config=config)
                        if os.path.exists(f'/tmp/{output_obj["jsonKey"]}'):
                            os.remove(f'/tmp/{output_obj["jsonKey"]}')
                            print('The json file removed!')
                        else:
                            print("The json file does not exist in the path: ", f'/tmp/{output_obj["jsonKey"]}')

            names_images_uploaded.append(output_obj)
            if not is_dev_local:
                print('Start to remove the file from tmp....')
                if os.path.exists(output_path[index]):
                    os.remove(output_path[index])
                    print('The file removed from the tmp location!')
                else:
                    print("The file does not exist in the path: ", output_path[index])

    except Exception as e:
        print(e)
        print('Error uploading file to output bucket')
        raise e

    return names_images_uploaded


if is_dev_local:
    lambda_handler({
        "bucket": "bucket",
        "key": "bucket",
        "download_path": "12.pdf"
    }, '')
