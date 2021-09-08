<?php
error_reporting(E_ALL);

$sql = "INSERT IGNORE INTO locations (acc, alt, lat, lon, tid, tst, vac, vel, p) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)";

$location = json_decode(file_get_contents('php://input'));

$user = $_SERVER['PHP_AUTH_USER'];
$password = $_SERVER['PHP_AUTH_PW'];
$database = $_GET['database'];

$conn = new mysqli('localhost', $user, $password, $database);
if ($conn->connect_error) {
  die("Connection failed: " . $conn->connect_error);
}

$stmt = $conn->prepare($sql);
$stmt->bind_param("iiddsiiid", $location->acc, $location->alt, $location->lat, $location->lon, $location->tid, $location->tst, $location->vac, $location->vel, $location->p);
$result = $stmt->execute();
print($result);
$stmt->close();
$conn->close();

?>
