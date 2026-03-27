cmake_minimum_required(VERSION 3.8)
project(sancho_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/AudioData.msg"
  "msg/BoolStamped.msg"
  "msg/ChunkMono.msg"
  "msg/ChunkStereo.msg"
  "msg/ConversationTurn.msg"
  "msg/Face.msg"
  "msg/FaceArray.msg"
  "msg/FaceDetection.msg"
  "msg/FaceDetectionArray.msg"
  "msg/FaceNameResponse.msg"
  "msg/FacePosition.msg"
  "msg/FaceQuestionResponse.msg"
  "msg/FaceRecognition.msg"
  "msg/FaceRecognitionArray.msg"
  "msg/FaceprintEvent.msg"
  "msg/GroupInfo.msg"
  "msg/InputTTS.msg"
  "msg/LLMLoadModelMsg.msg"
  "msg/LLMLoadUnloadResult.msg"
  "msg/Log.msg"
  "msg/ModelItem.msg"
  "msg/ModelSpeaker.msg"
  "msg/PersonPose.msg"
  "msg/PersonsPoses.msg"
  "msg/ProviderItem.msg"
  "msg/ProviderModel.msg"
  "msg/QuestionTTS.msg"
  "msg/R2WMessage.msg"
  "msg/SessionMessage.msg"
  "msg/SpeechLoadModelMsg.msg"
  "msg/SpeechLoadUnloadResult.msg"
  "msg/UserTranscription.msg"
  "msg/VADSegment.msg"
  "srv/StartInteraction.srv"
  "srv/EndInteraction.srv"
<<<<<<< HEAD:sancho_ws/src/sancho_interfaces/CMakeLists.txt
  "srv/ForceAttention.srv"
=======
>>>>>>> refactor:ros2_ws/src/sancho_interfaces/CMakeLists.txt
  "srv/AskUser.srv"
  "srv/Detection.srv"
  "srv/Embedding.srv"
  "srv/GetActiveModels.srv"
  "srv/GetCentralFaceCluster.srv"
  "srv/GetModels.srv"
  "srv/GetNoiseFloor.srv"
  "srv/GetString.srv"
  "srv/GreetPeople.srv"
  "srv/LLMLoadModel.srv"
  "srv/LLMUnloadModel.srv"
  "srv/Prompt.srv"
  "srv/R2WSubscribe.srv"
  "srv/Recognition.srv"
  "srv/STT.srv"
  "srv/STTGetActiveModel.srv"
  "srv/STTGetModels.srv"
  "srv/STTSetActiveModel.srv"
  "srv/SanchoPrompt.srv"
  "srv/SetActiveModel.srv"
  "srv/SetHome.srv"
  "srv/SetSessionParams.srv"
  "srv/SocialState.srv"
  "srv/SpeechLoadModel.srv"
  "srv/SpeechUnloadModel.srv"
  "srv/TTS.srv"
  "srv/TTSGetActiveModel.srv"
  "srv/TTSGetModels.srv"
  "srv/TTSSetActiveModel.srv"
  "srv/Training.srv"
  "srv/TriggerUserInteraction.srv"
  "action/PlayAudio.action"
  DEPENDENCIES geometry_msgs sensor_msgs std_msgs action_msgs
)

ament_package()
