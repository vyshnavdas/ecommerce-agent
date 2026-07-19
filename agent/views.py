from django.shortcuts import render
from .agent import agent
from django.http import JsonResponse
import json
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.http import StreamingHttpResponse
import os
import uuid
from langchain_core.messages import HumanMessage, AIMessage
import re
from django.contrib.admin.views.decorators import staff_member_required

@staff_member_required
def chat_page(request):
    return render(request, 'chat.html')

@csrf_exempt
def chat(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "Forbidden: Admin access required"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    data = json.loads(request.body)
    message = data.get("message", "")
    image_urls = data.get("image_urls", [])

    if image_urls:
        message += f"\nUploaded image URLs: {', '.join(image_urls)}"

    response = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"configurable": {"thread_id": "admin"}}
    )

    ai_msg = response["messages"][-1]
    if isinstance(ai_msg.content, list):
        ai_reply = " ".join(
            block.get("text", "")
            for block in ai_msg.content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        ai_reply = ai_msg.content

    return JsonResponse({"response": ai_reply})

@csrf_exempt
def upload_image(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "Forbidden: Admin access required"}, status=403)

    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    image = request.FILES.get("image")
    if not image:
        return JsonResponse({"error": "No image provided"}, status=400)

    ext = os.path.splitext(image.name)[1]
    filename = f"products/{uuid.uuid4()}{ext}"
    path = default_storage.save(filename, image)
    url = request.build_absolute_uri(f"/media/{path}")

    return JsonResponse({"url": url})

def chat_history(request):
    if not (request.user.is_authenticated and request.user.is_staff):
        return JsonResponse({"error": "Forbidden: Admin access required"}, status=403)

    config = {"configurable": {"thread_id": "admin"}}
    state = agent.get_state(config)
    messages = state.values.get("messages", [])[-20:]

    history = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            content = msg.content
            # extract image urls from message
            image_urls = re.findall(r'http\S+\.(?:jpg|jpeg|png|gif|webp)', content)
            # clean text
            text = re.sub(r'Uploaded image URLs:.*', '', content).strip()
            history.append({"role": "user", "content": text, "image_urls": image_urls})
        elif isinstance(msg, AIMessage):
            if isinstance(msg.content, list):
                text = " ".join(
                    block.get("text", "")
                    for block in msg.content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            else:
                text = msg.content
            if text:
                history.append({"role": "ai", "content": text, "image_urls": []})

    return JsonResponse({"history": history})