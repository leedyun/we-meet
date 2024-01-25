from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import datetime

app = Flask(__name__)
CORS(app)

# OpenAI API 키 설정
openai.api_key = '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'

# 대화 상태를 저장하는 딕셔너리
conversation_states = {}

reservations_data = {}

def save_reservation(user_id, reservation_info):
    """사용자의 예약 정보를 저장하는 함수"""
    if user_id not in reservations_data:
        reservations_data[user_id] = [reservation_info]
    else:
        reservations_data[user_id].append(reservation_info)


def get_reservations(user_id):
    """사용자의 예약 정보를 가져오는 함수"""
    return reservations_data.get(user_id, [])

def handle_reservation(state, user_input, user_id):
    if state["sub_step"] == "ask_departure":
        # 출발지를 저장하고 다음 단계로 넘어감
        state["departure"] = user_input
        response = "도착지를 입력해주세요."
        state["sub_step"] = "receive_destination"
    elif state["sub_step"] == "receive_destination":
        # 도착지를 저장하고 다음 단계로 넘어감
        state["destination"] = user_input
        response = "원하시는 예약 날짜와 시간을 알려주세요. (예: 2024-01-26 15:00)"
        state["sub_step"] = "receive_datetime"
    elif state["sub_step"] == "receive_datetime":
        try:
            # 날짜와 시간 형식을 검증하는 로직 (엄격하게 검사)
            datetime_obj = datetime.datetime.strptime(user_input, '%Y-%m-%d %H:%M')
            # 현재 시간 이후로 예약 가능하도록 체크
            if datetime_obj <= datetime.datetime.now():
                response = "예약은 현재 시간 이후로만 가능합니다. 다시 입력해주세요."
            else:
                state["datetime"] = datetime_obj
                response = "예약을 위한 이름과 전화번호를 알려주세요. (예: 홍길동, 010-1234-5678)"
                state["sub_step"] = "receive_contact"
        except ValueError:
            response = "날짜와 시간 형식이 올바르지 않습니다. 다시 입력해주세요. (예: 2024-01-26 15:00)"
    elif state["sub_step"] == "receive_contact":
    # 간단한 형식 검증
        if "," in user_input and len(user_input.split(",")) == 2:
            name, phone = user_input.split(",")
            state["name"] = name.strip()
            state["phone"] = phone.strip()

            # 예약 정보를 저장하는 부분
            reservation_info = {
                "departure": state["departure"],
                "destination": state["destination"],
                "datetime": state["datetime"],
                "name": state["name"],
                "phone": state["phone"]
            }
            save_reservation(user_id, reservation_info)  # 여기서 예약 정보를 저장

            response = "{}님,예약이 완료되었습니다. 예약 정보 : 전화번호 - {}, 출발지 - {}, 도착지 - {}, 예약시간 - {}".format(
                state["name"], state["phone"], state["departure"], state["destination"], state["datetime"].strftime("%Y-%m-%d %H:%M"))
            state["sub_step"] = "completed"
        else:
            response = "이름과 전화번호 형식이 올바르지 않습니다. 다시 입력해주세요."

    else:
        response = "예약 절차가 완료되었습니다. 12시 10분까지 {}로 나와주세요. 예상 소요시간은 20분이며, 다른 승객들과 동행할 수 있다는 점 유의해주세요. 다른 도움이 필요하시면 말씀해주세요.".format(
                state["departure"])
        state["step"] = "welcome"
        state["sub_step"] = None

    return response

# 조회 처리 함수
def handle_inquiry(state, user_id):
    response = ""

    if state["sub_step"] == "ask_contact":
        response = "예약하신 이름과 전화번호를 입력해주세요."
        state["sub_step"] = "show_reservations"
    elif state["sub_step"] == "show_reservations":
        reservations = get_reservations(user_id)
        if not reservations:
            response = "예약 내역이 없습니다."
        else:
            response = "귀하의 예약 내역은 다음과 같습니다:\n" + "\n".join(
                [f"{idx+1}. 출발지: {res['departure']}, 도착지: {res['destination']}, 예약시간: {res['datetime']}" for idx, res in enumerate(reservations)])
        state["sub_step"] = "completed"
        state["step"] = "welcome"

    return response, False


# 수정 처리 함수
def handle_modification(state, user_id, user_input):
    response = ""  # 기본적으로 빈 문자열로 초기화
    reservations = get_reservations(user_id)
    if state["sub_step"] == "choose_reservation_to_modify":
        if not reservations:
            response = "예약 내역이 없습니다."
        else:
            response = "수정하실 예약을 선택해주세요:\n" + "\n".join(
                [f"{idx+1}. 출발지: {res['departure']}, 도착지: {res['destination']}, 예약시간: {res['datetime']}" for idx, res in enumerate(reservations)])
        state["sub_step"] = "modify_reservation"
    elif state["sub_step"] == "modify_reservation":
        if user_input.isdigit():
            # 사용자가 선택한 예약을 수정하는 로직
            selected_idx = int(user_input) - 1
            reservations = get_reservations(user_id)
            if selected_idx < 0 or selected_idx >= len(reservations):
                response = "잘못된 선택입니다. 다시 선택해주세요."
            else:
                # 예약 수정을 위한 추가 정보 요청
                response = "수정할 정보를 입력해주세요. 예: 출발지 변경, 도착지 변경"
                state["sub_step"] = "receive_modified_info"
                state["selected_reservation"] = selected_idx
        else:
            response = "잘못된 입력입니다. 예약 번호를 숫자로 입력해주세요."
    elif state["sub_step"] == "receive_modified_info":
        selected_reservation = reservations[state["selected_reservation"]]

        # 출발지 변경 요청 처리
        if user_input.startswith("출발지 변경:"):
            new_departure = user_input.split("출발지 변경:")[1].strip()
            selected_reservation["departure"] = new_departure
            response = "출발지가 수정되었습니다."

        # 도착지 변경 요청 처리
        elif user_input.startswith("도착지 변경:"):
            new_destination = user_input.split("도착지 변경:")[1].strip()
            selected_reservation["destination"] = new_destination
            response = "도착지가 수정되었습니다."

        # 시간 변경 요청 처리
        elif user_input.startswith("시간 변경:"):
            try:
                new_datetime = datetime.datetime.strptime(user_input.split("시간 변경:")[1].strip(), '%Y-%m-%d %H:%M')
                selected_reservation["datetime"] = new_datetime
                response = "예약 시간이 수정되었습니다."
            except ValueError:
                response = "날짜와 시간 형식이 올바르지 않습니다. 다시 입력해주세요."

        # 기타 요청 처리
        else:
            response = "지원하지 않는 수정 요청입니다. 다시 입력해주세요."

        state["sub_step"] = "completed"

    return response, state["sub_step"] == "completed"


# 취소 처리 함수 
def handle_cancellation(state, user_id, user_input):
    response = ""  # 기본적으로 빈 문자열로 초기화
    if state["sub_step"] == "ask_contact":
        response = "예약하신 이름과 전화번호를 입력해주세요."
        state["sub_step"] = "choose_reservation_to_cancel"
    elif state["sub_step"] == "choose_reservation_to_cancel":
        reservations = get_reservations(user_id)
        if not reservations:
            response = "예약 내역이 없습니다."
        else:
            response = "취소하실 예약을 선택해주세요:\n" + "\n".join(
                [f"{idx+1}. 출발지: {res['departure']}, 도착지: {res['destination']}, 예약시간: {res['datetime']}" for idx, res in enumerate(reservations)])
        state["sub_step"] = "cancel_reservation"
    elif state["sub_step"] == "cancel_reservation":
        # 예약 취소 처리
        selected_idx = int(user_input) - 1
        reservations = get_reservations(user_id)
        if selected_idx < 0 or selected_idx >= len(reservations):
            response = "잘못된 선택입니다. 다시 선택해주세요."
        else:
            reservations.pop(selected_idx)  # 선택한 예약 취소
            response = "선택하신 예약이 성공적으로 취소되었습니다."
            state["sub_step"] = "completed"

    return response, state["sub_step"] == "completed"

@app.route('/')
def home():
    return "Welcome to the Chatbot!"


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_id = data['user_id']  # 사용자 식별자
    user_input = data['message']
    
    # 사용자의 현재 대화 상태 가져오기
    state = conversation_states.get(user_id, {"step": "welcome", "sub_step": None})

    # 대화 상태에 따른 로직 처리
    if state["step"] == "welcome":
        response = "안녕하세요. drt 예약에 도움이 필요하신가요? 예약/조회/수정/취소 중에 골라주세요"
        state["step"] = "choose_service"
    elif state["step"] == "choose_service":
        if "예약" in user_input:
            state["step"] = "reservation"
            state["sub_step"] = "ask_departure"
            response = "출발지를 입력해주세요."
        elif "조회" in user_input:
            state["step"] = "inquiry"
            state["sub_step"] = "ask_contact"
            response, return_to_welcome = handle_inquiry(state, user_id)
        elif "수정" in user_input:
            state["step"] = "modification"
            state["sub_step"] = "choose_reservation_to_modify"
            response, return_to_welcome = handle_modification(state, user_id, user_input)
        elif "취소" in user_input:
            state["step"] = "cancellation"
            state["sub_step"] = "ask_contact"
            response, return_to_welcome = handle_cancellation(state, user_id, user_input)
        else:
            response = "이해하지 못했습니다. 다시 선택해주세요."
    elif state["step"] in ["reservation", "inquiry", "modification", "cancellation"]:
        # 각 서비스별 처리 함수 호출
        if state["step"] == "reservation":
            response = handle_reservation(state, user_input, user_id)
        elif state["step"] == "inquiry":
            response, return_to_welcome = handle_inquiry(state, user_id)
            if return_to_welcome:
                state["step"] = "welcome"  # 초기 상태로 돌아감
        elif state["step"] == "modification":
            response, return_to_welcome = handle_modification(state, user_id, user_input)
            if return_to_welcome:
                state["step"] = "welcome"  # 초기 상태로 돌아감
        elif state["step"] == "cancellation":
            response, return_to_welcome = handle_cancellation(state, user_id, user_input)
            if return_to_welcome:
                state["step"] = "welcome"  # 초기 상태로 돌아감


    # 사용자의 대화 상태 업데이트
    conversation_states[user_id] = state

    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)