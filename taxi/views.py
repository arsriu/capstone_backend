import requests
import xml.etree.ElementTree as ET
from django.shortcuts import render
import csv
import os
from django.conf import settings
from django.http import JsonResponse

# HTML 템플릿을 렌더링하는 뷰
def moving_taxi_view(request):
    return render(request, 'moving_taxi.html')

def taxi_location_json(request):
    # CSV 파일 경로 설정
    csv_file_path = os.path.join(settings.BASE_DIR, 'taxi_location.csv')
    results = []  # 각 link_id와 위치 정보를 저장할 리스트

    # CSV 파일에서 link_id, s_lat, s_long, d_lat, d_long 값 읽기
    try:
        with open(csv_file_path, newline='', encoding='ISO-8859-1') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                link_id = row.get('link_id')
                s_lat = row.get('s_lat')
                s_long = row.get('s_long')
                d_lat = row.get('d_lat')
                d_long = row.get('d_long')

                if link_id:  # link_id 값이 있는 경우에만 추가
                    # API 호출 URL 구성
                    api_url = f'https://openapigits.gg.go.kr/api/rest/getRoadLinkTrafficInfo?serviceKey=???linkId={link_id}'
                    cong_grade_value = "N/A"  # 기본값 설정

                    try:
                        # 외부 API 호출
                        response = requests.get(api_url)
                        if response.status_code == 200:
                            # XML 응답을 파싱하여 congGrade 값 추출
                            root = ET.fromstring(response.text)
                            item = root.find(".//msgBody/itemList/congGrade")
                            if item is not None:
                                cong_grade_value = item.text
                            else:
                                cong_grade_value = "congGrade not found"
                        else:
                            cong_grade_value = f"Failed to fetch data. Status code: {response.status_code}"
                    except requests.RequestException as e:
                        cong_grade_value = f"Error fetching data: {str(e)}"

                    # 각 link_id, 위치 정보, congGrade 값을 results 리스트에 추가
                    results.append({
                        'link_id': link_id,
                        's_lat': s_lat,
                        's_long': s_long,
                        'd_lat': d_lat,
                        'd_long': d_long,
                        'cong_grade': cong_grade_value
                    })
    except FileNotFoundError:
        return JsonResponse({'error': "CSV file not found."}, status=404)

    # JSON 형식으로 결과 반환
    return JsonResponse(results, safe=False)
